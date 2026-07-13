#!/usr/bin/env python3
"""
ai_hedge_fund_adapter.py — Run virattt/ai-hedge-fund on BotTrade scenarios.

This adapter runs locally inside an ai-hedge-fund checkout. BotTrade provides
the run lifecycle, market simulation, scoring, and public result page. The
caller supplies every external-data or model credential used by ai-hedge-fund.
BotTrade does not fetch, store, or pay for news, fundamentals, or model calls.

Modes:
  as-of      Run the full ai-hedge-fund workflow. The active BotTrade scenario
             date is passed to it as end_date, and its configured providers run
             locally with the caller's credentials. This is self-attested:
             BotTrade cannot independently verify a third-party provider's data.
  technical  Run ai-hedge-fund's technical-analysis functions on BotTrade's
             visible OHLCV bars only. This path makes no external-data calls.

Setup:
  git clone https://github.com/virattt/ai-hedge-fund.git
  cd ai-hedge-fund
  poetry install
  poetry run pip install 'bottrade[ai-hedge-fund]'
  export BOTTRADE_API_KEY="bt_your_key_here"

Examples:
  python ai_hedge_fund_adapter.py --scenario tech-2024-q2 --publish
  python ai_hedge_fund_adapter.py --mode technical --scenario tech-2024-q2
  python ai_hedge_fund_adapter.py --mode as-of --analysts technical_analyst,news_sentiment_analyst
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from bottrade import AgentInfo, APIError
from bottrade import BotTradeClient as SDKClient

API_BASE = os.environ.get("BOTTRADE_API", "https://bot-trade.org")
MIN_TECHNICAL_HISTORY = 130


class BotTradeClient:
    """Compatibility wrapper over the maintained, typed BotTrade SDK."""

    def __init__(
        self,
        api_key: str,
        base: str = API_BASE,
        agent_info: AgentInfo | None = None,
    ):
        self.sdk = SDKClient(api_key, base_url=base)
        self.agent_info = agent_info

    def __enter__(self) -> BotTradeClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.sdk.close()

    def scenario(self, slug: str) -> dict[str, Any]:
        return self.sdk.get_scenario(slug).model_dump(mode="json")

    def start_run(self, slug: str, bot_name: str) -> dict[str, Any]:
        return self.sdk.start_run(
            slug, bot_name=bot_name, agent_info=self.agent_info
        ).model_dump(mode="json")

    def snapshot(self, run_id: str) -> dict[str, Any]:
        return self.sdk.get_run(run_id).model_dump(mode="json")

    def market(self, run_id: str, symbols: list[str], lookback: int) -> dict[str, Any]:
        return self.sdk.get_market(run_id, symbols=symbols, lookback=lookback).model_dump(
            mode="json"
        )

    def queue_trade(
        self,
        run_id: str,
        symbol: str,
        side: str,
        quantity: float,
        reasoning: str,
    ) -> None:
        self.sdk.queue_trade(
            run_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            reasoning=reasoning,
        )

    def step(self, run_id: str) -> dict[str, Any]:
        return self.sdk.step(run_id).model_dump(mode="json")

    def results(self, run_id: str) -> dict[str, Any]:
        return self.sdk.get_results(run_id).model_dump(mode="json")

    def publish(self, run_id: str) -> None:
        self.sdk.publish_run(run_id, confirm=True)


def finite_float(value: Any, default: float = 0.0) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default


def parse_sim_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as error:
        raise RuntimeError(f"invalid BotTrade sim_time: {value!r}") from error
    return parsed.astimezone(UTC)


def current_positions(snapshot: dict[str, Any]) -> dict[str, float]:
    positions: dict[str, float] = {}
    for position in snapshot.get("positions") or []:
        symbol = position.get("symbol")
        quantity = finite_float(position.get("quantity"))
        if symbol and quantity:
            positions[str(symbol)] = quantity
    return positions


def current_equity(snapshot: dict[str, Any]) -> float:
    last_equity = snapshot.get("last_equity") or {}
    equity = finite_float(last_equity.get("equity"))
    if equity > 0:
        return equity
    run = snapshot.get("run") or {}
    return max(0.0, finite_float(run.get("cash") or run.get("starting_cash")))


def portfolio_for_ai_hedge_fund(
    snapshot: dict[str, Any],
    universe: list[str],
    leverage_cap: float,
) -> dict[str, Any]:
    """Map BotTrade's signed positions into ai-hedge-fund's portfolio shape."""
    positions = current_positions(snapshot)
    raw_positions = {item.get("symbol"): item for item in snapshot.get("positions") or []}
    portfolio_positions: dict[str, dict[str, float]] = {}
    realized_gains: dict[str, dict[str, float]] = {}
    for symbol in universe:
        quantity = positions.get(symbol, 0.0)
        average_cost = finite_float((raw_positions.get(symbol) or {}).get("avg_cost"))
        portfolio_positions[symbol] = {
            "long": max(quantity, 0.0),
            "short": max(-quantity, 0.0),
            "long_cost_basis": average_cost if quantity > 0 else 0.0,
            "short_cost_basis": average_cost if quantity < 0 else 0.0,
            "short_margin_used": 0.0,
        }
        realized_gains[symbol] = {"long": 0.0, "short": 0.0}

    run = snapshot.get("run") or {}
    return {
        "cash": finite_float(run.get("cash")),
        "equity": current_equity(snapshot),
        "margin_requirement": 1.0 / leverage_cap if leverage_cap > 0 else 1.0,
        "margin_used": 0.0,
        "positions": portfolio_positions,
        "realized_gains": realized_gains,
    }


def order_from_decision(
    symbol: str,
    decision: Any,
    positions: dict[str, float],
    *,
    short_enabled: bool,
) -> dict[str, Any] | None:
    """Turn an upstream action into an order BotTrade will accept."""
    if not isinstance(decision, dict):
        return None
    side = str(decision.get("action", "hold")).lower()
    quantity = finite_float(decision.get("quantity"))
    if side not in {"buy", "sell", "short", "cover"} or quantity <= 0:
        return None

    current = positions.get(symbol, 0.0)
    if side == "sell":
        quantity = min(quantity, max(current, 0.0))
    elif side == "cover":
        quantity = min(quantity, max(-current, 0.0))
    elif side == "short" and not short_enabled:
        return None
    if quantity <= 0:
        return None

    reasoning = str(decision.get("reasoning") or "ai-hedge-fund as-of decision")
    return {
        "symbol": symbol,
        "side": side,
        "quantity": round(quantity, 6),
        "reasoning": f"ai-hedge-fund as-of: {reasoning}",
    }


class AsOfStrategy:
    """Adapter for ai-hedge-fund's full local workflow and caller-owned data."""

    def __init__(
        self,
        *,
        history_days: int,
        model_name: str,
        model_provider: str,
        selected_analysts: list[str],
        runner: Callable[..., dict[str, Any]] | None = None,
    ):
        self.history_days = history_days
        self.model_name = model_name
        self.model_provider = model_provider
        self.selected_analysts = selected_analysts
        self.runner = runner or self._load_runner()

    @staticmethod
    def _load_runner() -> Callable[..., dict[str, Any]]:
        try:
            from src.main import run_hedge_fund
        except ImportError as error:
            raise RuntimeError(
                "Could not import ai-hedge-fund. Run this script from the root of an "
                "ai-hedge-fund checkout after `poetry install`."
            ) from error
        return run_hedge_fund

    def decide(
        self,
        snapshot: dict[str, Any],
        scenario: dict[str, Any],
    ) -> dict[str, Any]:
        run = snapshot.get("run") or {}
        sim_time = parse_sim_time(str(run.get("sim_time")))
        end_date = sim_time.date().isoformat()
        start_date = (sim_time - timedelta(days=self.history_days)).date().isoformat()
        leverage_cap = finite_float(scenario.get("leverage_cap"), 1.0)
        response = self.runner(
            tickers=list(scenario["universe"]),
            start_date=start_date,
            end_date=end_date,
            portfolio=portfolio_for_ai_hedge_fund(
                snapshot, list(scenario["universe"]), leverage_cap
            ),
            show_reasoning=False,
            selected_analysts=self.selected_analysts,
            model_name=self.model_name,
            model_provider=self.model_provider,
        )
        decisions = response.get("decisions") if isinstance(response, dict) else None
        return decisions if isinstance(decisions, dict) else {}


@dataclass(frozen=True)
class Signal:
    symbol: str
    direction: str
    confidence: float
    components: tuple[tuple[str, str, float], ...] = ()

    @property
    def score(self) -> float:
        if self.direction == "bullish":
            return self.confidence
        if self.direction == "bearish":
            return -self.confidence
        return 0.0


class TechnicalStrategy:
    """ai-hedge-fund technical functions evaluated only on BotTrade bars."""

    REQUIRED_FUNCTIONS = (
        "calculate_trend_signals",
        "calculate_mean_reversion_signals",
        "calculate_momentum_signals",
        "calculate_volatility_signals",
        "calculate_stat_arb_signals",
        "weighted_signal_combination",
    )

    def __init__(self, technical_module: Any | None = None):
        self.technical = technical_module or self._load_module()
        missing = [
            name
            for name in self.REQUIRED_FUNCTIONS
            if not callable(getattr(self.technical, name, None))
        ]
        if missing:
            raise RuntimeError("ai-hedge-fund technical functions missing: " + ", ".join(missing))

    @staticmethod
    def _load_module() -> Any:
        try:
            from src.agents import technicals
        except ImportError as error:
            raise RuntimeError(
                "Could not import ai-hedge-fund. Run this script from the root of an "
                "ai-hedge-fund checkout after `poetry install`."
            ) from error
        return technicals

    def analyze(self, bars_by_symbol: dict[str, list[dict[str, Any]]]) -> dict[str, Signal]:
        weights = {
            "trend": 0.25,
            "mean_reversion": 0.20,
            "momentum": 0.25,
            "volatility": 0.15,
            "stat_arb": 0.15,
        }
        signals: dict[str, Signal] = {}
        for symbol, bars in bars_by_symbol.items():
            if len(bars) < MIN_TECHNICAL_HISTORY:
                continue
            try:
                frame = bars_to_frame(bars)
                components = {
                    "trend": self.technical.calculate_trend_signals(frame.copy(deep=True)),
                    "mean_reversion": self.technical.calculate_mean_reversion_signals(
                        frame.copy(deep=True)
                    ),
                    "momentum": self.technical.calculate_momentum_signals(frame.copy(deep=True)),
                    "volatility": self.technical.calculate_volatility_signals(
                        frame.copy(deep=True)
                    ),
                    "stat_arb": self.technical.calculate_stat_arb_signals(frame.copy(deep=True)),
                }
                combined = self.technical.weighted_signal_combination(components, weights)
            except Exception as error:
                print(f"  ! {symbol}: technical analysis failed: {error}", file=sys.stderr)
                continue
            direction = str(combined.get("signal", "neutral"))
            if direction not in {"bullish", "bearish", "neutral"}:
                direction = "neutral"
            component_summary = tuple(
                (
                    name,
                    str(component.get("signal", "neutral")),
                    max(0.0, finite_float(component.get("confidence"))),
                )
                for name, component in components.items()
            )
            signals[symbol] = Signal(
                symbol,
                direction,
                max(0.0, finite_float(combined.get("confidence"))),
                component_summary,
            )
        return signals


def bars_to_frame(bars: list[dict[str, Any]]):
    try:
        import pandas as pd
    except ImportError as error:
        raise RuntimeError(
            "pandas is required; install ai-hedge-fund with `poetry install`."
        ) from error

    frame = pd.DataFrame(bars, columns=["ts", "open", "high", "low", "close", "volume"])
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True, errors="coerce")
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna().drop_duplicates(subset="ts").sort_values("ts")
    if len(frame) < MIN_TECHNICAL_HISTORY:
        raise ValueError(f"need {MIN_TECHNICAL_HISTORY} valid bars, got {len(frame)}")
    return frame.set_index("ts")


def latest_closes(bars_by_symbol: dict[str, list[dict[str, Any]]]) -> dict[str, float]:
    closes: dict[str, float] = {}
    for symbol, bars in bars_by_symbol.items():
        if bars:
            close = finite_float(bars[-1].get("close"))
            if close > 0:
                closes[symbol] = close
    return closes


def quantity_for_notional(symbol: str, notional: float, price: float) -> float:
    quantity = notional / price if price > 0 else 0.0
    return round(quantity, 6) if "/" in symbol else float(math.floor(quantity))


def technical_targets(
    signals: dict[str, Signal],
    positions: dict[str, float],
    closes: dict[str, float],
    equity: float,
    *,
    short_enabled: bool,
    max_positions: int,
    gross_exposure: float,
    min_confidence: float,
) -> dict[str, float]:
    targets = {symbol: 0.0 for symbol in positions if symbol in closes}
    candidates = [
        signal
        for signal in signals.values()
        if signal.confidence >= min_confidence
        and signal.symbol in closes
        and (signal.direction == "bullish" or (short_enabled and signal.direction == "bearish"))
    ]
    candidates.sort(key=lambda signal: (-abs(signal.score), signal.symbol))
    if not candidates or equity <= 0:
        return targets

    per_position_notional = equity * gross_exposure / max_positions
    for signal in candidates[:max_positions]:
        quantity = quantity_for_notional(
            signal.symbol, per_position_notional, closes[signal.symbol]
        )
        if quantity > 0:
            targets[signal.symbol] = quantity if signal.direction == "bullish" else -quantity
    return targets


def orders_for_targets(
    positions: dict[str, float],
    targets: dict[str, float],
    signals: dict[str, Signal],
) -> list[dict[str, Any]]:
    """Reverse positions in two decisions so closing fills before reopening."""
    orders: list[dict[str, Any]] = []
    for symbol in sorted(set(positions) | set(targets)):
        current = positions.get(symbol, 0.0)
        target = targets.get(symbol, 0.0)
        signal = signals.get(symbol, Signal(symbol, "neutral", 0.0))
        reasoning = technical_decision_reason(signal, current, target)
        if current > 0 and target < 0:
            orders.append(make_order(symbol, "sell", current, reasoning))
        elif current < 0 and target > 0:
            orders.append(make_order(symbol, "cover", -current, reasoning))
        elif current >= 0 and target > current:
            orders.append(make_order(symbol, "buy", target - current, reasoning))
        elif current > 0 and target < current:
            orders.append(make_order(symbol, "sell", current - target, reasoning))
        elif current <= 0 and target < current:
            orders.append(make_order(symbol, "short", current - target, reasoning))
        elif current < 0 and target > current:
            orders.append(make_order(symbol, "cover", target - current, reasoning))
    return [order for order in orders if order["quantity"] > 0]


def technical_decision_reason(signal: Signal, current: float, target: float) -> str:
    factors = ", ".join(
        f"{name}={direction} {confidence:.0%}" for name, direction, confidence in signal.components
    )
    reason = (
        f"ai-hedge-fund decision: {signal.direction} {signal.confidence:.0%}; "
        f"position {current:g} -> target {target:g}"
    )
    return reason + (f"; factors: {factors}" if factors else "")


def make_order(symbol: str, side: str, quantity: float, reasoning: str) -> dict[str, Any]:
    return {"symbol": symbol, "side": side, "quantity": round(quantity, 6), "reasoning": reasoning}


class Client(Protocol):
    def scenario(self, slug: str) -> dict[str, Any]: ...
    def start_run(self, slug: str, bot_name: str) -> dict[str, Any]: ...
    def snapshot(self, run_id: str) -> dict[str, Any]: ...
    def market(self, run_id: str, symbols: list[str], lookback: int) -> dict[str, Any]: ...
    def queue_trade(
        self, run_id: str, symbol: str, side: str, quantity: float, reasoning: str
    ) -> None: ...
    def step(self, run_id: str) -> dict[str, Any]: ...
    def results(self, run_id: str) -> dict[str, Any]: ...
    def publish(self, run_id: str) -> None: ...


@dataclass(frozen=True)
class RunConfig:
    scenario_slug: str
    bot_name: str
    mode: str
    decide_every: int
    lookback: int
    max_bars: int
    max_positions: int
    gross_exposure: float
    min_confidence: float
    publish: bool
    run_id: str | None = None


def queue_orders(client: Client, run_id: str, orders: list[dict[str, Any]]) -> None:
    for order in orders:
        try:
            client.queue_trade(run_id, **order)
            print(f"  queued {order['side']} {order['quantity']:g} {order['symbol']}")
        except APIError as error:
            if error.status != 400:
                raise
            summary = f"{order['side']} {order['quantity']:g} {order['symbol']}: {error.detail}"
            print(f"  ! rejected {summary}")


def execute_benchmark(
    client: Client,
    config: RunConfig,
    *,
    as_of_strategy: AsOfStrategy | None = None,
    technical_strategy: TechnicalStrategy | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    scenario = client.scenario(config.scenario_slug)
    universe = list(scenario["universe"])
    short_enabled = bool(scenario.get("short_enabled"))
    leverage_cap = finite_float(scenario.get("leverage_cap"), 1.0)
    if config.run_id:
        run_id = config.run_id
        run = client.snapshot(run_id).get("run") or {"id": run_id}
    else:
        run = client.start_run(config.scenario_slug, config.bot_name)
        run_id = run["id"]
    print(f"Scenario: {scenario['slug']} ({scenario.get('name', '')})")
    print(f"Run: {run_id}")
    print(f"Mode: {config.mode}")

    completed = False
    for bar_index in range(config.max_bars):
        if bar_index % config.decide_every == 0:
            snapshot = client.snapshot(run_id)
            positions = current_positions(snapshot)
            if config.mode == "as-of":
                if as_of_strategy is None:
                    raise RuntimeError("as-of strategy was not configured")
                decisions = as_of_strategy.decide(snapshot, scenario)
                orders = [
                    order
                    for symbol, decision in decisions.items()
                    if symbol in universe
                    for order in [
                        order_from_decision(
                            symbol, decision, positions, short_enabled=short_enabled
                        )
                    ]
                    if order is not None
                ]
            else:
                if technical_strategy is None:
                    raise RuntimeError("technical strategy was not configured")
                market = client.market(run_id, universe, config.lookback)
                bars = market.get("bars") or {}
                signals = technical_strategy.analyze(bars)
                targets = technical_targets(
                    signals,
                    positions,
                    latest_closes(bars),
                    current_equity(snapshot),
                    short_enabled=short_enabled,
                    max_positions=config.max_positions,
                    gross_exposure=min(config.gross_exposure, leverage_cap),
                    min_confidence=config.min_confidence,
                )
                orders = orders_for_targets(positions, targets, signals)
            queue_orders(client, run_id, orders)

        outcome = client.step(run_id)
        if outcome.get("done") or outcome.get("liquidated"):
            completed = True
            break

    if not completed:
        raise RuntimeError(
            f"run {run_id} did not finish before --max-bars={config.max_bars}; "
            f"resume with --run-id {run_id}"
        )
    results = client.results(run_id)
    print_results(results)
    if config.publish:
        client.publish(run_id)
        print(f"Published: https://bot-trade.org/run/{run_id}")
    return run, results


def print_results(results: dict[str, Any]) -> None:
    print("\nResults")
    print(f"  return:       {finite_float(results.get('return_pct')):+.2f}%")
    print(f"  final equity: ${finite_float(results.get('final_equity')):,.2f}")
    print(f"  Sharpe:       {results.get('sharpe')}")
    print(f"  Sortino:      {results.get('sortino')}")
    print(f"  max drawdown: {results.get('max_drawdown')}")
    print(f"  trades:       {results.get('trade_count')}")
    print(f"  liquidated:   {results.get('liquidated')}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ai-hedge-fund through a BotTrade benchmark.")
    parser.add_argument(
        "--bot-api-key",
        default=os.environ.get("BOTTRADE_API_KEY") or os.environ.get("BOT_API_KEY"),
        help="BotTrade API key (defaults to BOTTRADE_API_KEY, then BOT_API_KEY).",
    )
    parser.add_argument("--api-base", default=API_BASE, help="BotTrade API base URL.")
    parser.add_argument("--scenario", default="tech-2024-q2", help="BotTrade scenario slug.")
    parser.add_argument("--bot-name", help="Leaderboard display name.")
    parser.add_argument("--mode", choices=["as-of", "technical"], default="as-of")
    parser.add_argument(
        "--decide-every", type=int, default=24, help="Make a decision every N bars."
    )
    parser.add_argument(
        "--max-bars", type=int, default=100_000, help="Safety cap for simulator steps."
    )
    parser.add_argument("--publish", action="store_true", help="Publish the completed result.")
    parser.add_argument(
        "--run-id", help="Resume an existing active BotTrade run instead of starting a new one."
    )
    parser.add_argument(
        "--history-days",
        type=int,
        default=180,
        help="External as-of data history supplied to ai-hedge-fund.",
    )
    parser.add_argument(
        "--model", default="gpt-4.1", help="ai-hedge-fund model name in as-of mode."
    )
    parser.add_argument(
        "--provider", default="OpenAI", help="ai-hedge-fund model provider in as-of mode."
    )
    parser.add_argument(
        "--upstream-version",
        default="2026.7.10",
        help="ai-hedge-fund version recorded with the run.",
    )
    parser.add_argument(
        "--source-revision",
        default="09dd33167bd6b4ea63ae32e7246e70e80632cc81",
        help="ai-hedge-fund commit recorded with the run.",
    )
    parser.add_argument(
        "--analysts", default="", help="Comma-separated ai-hedge-fund analyst keys in as-of mode."
    )
    parser.add_argument(
        "--lookback", type=int, default=180, help="BotTrade bars available to technical mode."
    )
    parser.add_argument(
        "--max-positions", type=int, default=4, help="Maximum target positions in technical mode."
    )
    parser.add_argument(
        "--gross-exposure",
        type=float,
        default=0.80,
        help="Maximum target notional divided by equity in technical mode.",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.15,
        help="Minimum technical confidence required to open a position.",
    )
    args = parser.parse_args(argv)
    if not args.bot_api_key:
        parser.error("--bot-api-key, BOTTRADE_API_KEY, or BOT_API_KEY is required")
    if args.decide_every < 1 or args.max_bars < 1 or args.history_days < 1:
        parser.error("--decide-every, --max-bars, and --history-days must be at least 1")
    if args.mode == "technical" and args.lookback < MIN_TECHNICAL_HISTORY:
        parser.error(f"--lookback must be at least {MIN_TECHNICAL_HISTORY} in technical mode")
    if args.max_positions < 1 or not 0 < args.gross_exposure <= 1:
        parser.error("--max-positions must be at least 1 and --gross-exposure must be in (0, 1]")
    if not 0 <= args.min_confidence <= 1:
        parser.error("--min-confidence must be between 0 and 1")
    args.bot_name = args.bot_name or f"ai-hedge-fund {args.mode}"
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = RunConfig(
        scenario_slug=args.scenario,
        bot_name=args.bot_name,
        mode=args.mode,
        decide_every=args.decide_every,
        lookback=args.lookback,
        max_bars=args.max_bars,
        max_positions=args.max_positions,
        gross_exposure=args.gross_exposure,
        min_confidence=args.min_confidence,
        publish=args.publish,
        run_id=args.run_id,
    )
    try:
        as_of = None
        technical = None
        if args.mode == "as-of":
            analysts = [analyst.strip() for analyst in args.analysts.split(",") if analyst.strip()]
            as_of = AsOfStrategy(
                history_days=args.history_days,
                model_name=args.model,
                model_provider=args.provider,
                selected_analysts=analysts,
            )
        else:
            technical = TechnicalStrategy()
        info = AgentInfo(
            name=args.bot_name,
            framework="ai-hedge-fund",
            model=args.model if args.mode == "as-of" else None,
            version=args.upstream_version,
            source_url="https://github.com/virattt/ai-hedge-fund",
            source_revision=args.source_revision,
            config={
                "mode": args.mode,
                "decide_every": args.decide_every,
                "lookback": args.lookback,
                "analysts": [item.strip() for item in args.analysts.split(",") if item.strip()],
            },
        )
        with BotTradeClient(args.bot_api_key, args.api_base, info) as client:
            execute_benchmark(
                client,
                config,
                as_of_strategy=as_of,
                technical_strategy=technical,
            )
    except (APIError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
