"""Small, deterministic workflows shared by the CLI and examples."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .client import BotTradeClient
from .errors import IncompleteRunError
from .models import Results, Run, Scenario

TERMINAL_RUN_STATUSES = frozenset({"completed", "done", "liquidated"})


@dataclass(frozen=True, slots=True)
class BenchmarkOutcome:
    """Identity and final metrics for one completed benchmark."""

    run_id: str
    scenario: Scenario
    results: Results
    published: bool
    bars_advanced: int | None

    @property
    def return_pct(self) -> float:
        """Final percentage return."""

        return self.results.return_pct

    @property
    def final_equity(self) -> float:
        """Final marked portfolio equity."""

        return self.results.final_equity

    @property
    def sharpe(self) -> float | None:
        """Final Sharpe ratio, when defined."""

        return self.results.sharpe

    @property
    def max_drawdown(self) -> float | None:
        """Maximum drawdown as a decimal fraction, when defined."""

        return self.results.max_drawdown


def require_completed_results(client: BotTradeClient, run_id: str) -> Results:
    """Return final metrics only after independently verifying terminal state."""

    snapshot = client.get_run(run_id)
    if snapshot.run.status.lower() not in TERMINAL_RUN_STATUSES:
        raise IncompleteRunError(
            f"Run {run_id} is {snapshot.run.status!r}, not complete. Resume that run; "
            "do not start a replacement if reproducibility matters."
        )
    return client.get_results(run_id)


def run_buy_and_hold(
    client: BotTradeClient,
    *,
    scenario_slug: str,
    quantity: float = 10,
    max_bars: int = 10_000,
    bot_name: str = "BotTrade Python buy-and-hold",
    publish: bool = False,
    on_started: Callable[[Run], None] | None = None,
) -> BenchmarkOutcome:
    """Create, advance, finish, score, and optionally publish one benchmark."""

    if quantity <= 0:
        raise ValueError("quantity must be greater than zero")
    if max_bars < 1:
        raise ValueError("max_bars must be at least one")

    scenario = client.get_scenario(scenario_slug)
    run = client.start_run(scenario.slug, bot_name=bot_name)
    if on_started is not None:
        on_started(run)
    symbol = scenario.benchmark_symbol or scenario.universe[0]
    client.queue_trade(
        run.id,
        symbol=symbol,
        side="buy",
        quantity=quantity,
        reasoning="Reference strategy: buy the scenario benchmark and hold.",
    )

    bars_advanced = 0
    for _ in range(max_bars):
        step = client.step(run.id)
        bars_advanced += step.bars_advanced
        if step.done or step.liquidated:
            break
    else:
        raise IncompleteRunError(
            f"Run {run.id} did not finish before max_bars={max_bars}. "
            f"Resume and inspect this run; run_id={run.id}"
        )

    results = require_completed_results(client, run.id)
    if publish:
        results = client.publish_run(run.id, confirm=True)
    return BenchmarkOutcome(run.id, scenario, results, publish, bars_advanced)


def run(
    scenario: str = "sandbox-nov-2024",
    *,
    quantity: float = 10,
    max_bars: int = 10_000,
    bot_name: str = "BotTrade Python buy-and-hold",
    publish: bool = False,
    api_key: str | None = None,
    timeout: float = 45.0,
    on_started: Callable[[Run], None] | None = None,
) -> BenchmarkOutcome:
    """Run the complete reference strategy as a one-call library API.

    Credentials come from ``api_key`` when supplied, otherwise from
    ``BOTTRADE_API_KEY`` (or the legacy ``BOT_API_KEY``) through
    :meth:`BotTradeClient.from_env`. Results remain private unless
    ``publish=True`` is explicitly passed.
    """

    client = (
        BotTradeClient(api_key, timeout=timeout)
        if api_key is not None
        else BotTradeClient.from_env(timeout=timeout)
    )
    with client:
        return run_buy_and_hold(
            client,
            scenario_slug=scenario,
            quantity=quantity,
            max_bars=max_bars,
            bot_name=bot_name,
            publish=publish,
            on_started=on_started,
        )


def format_results(outcome: BenchmarkOutcome, *, run_url: str | None = None) -> str:
    """Render the same auditable summary in the package CLI and examples."""

    results = outcome.results

    def metric(value: float | None, *, percent: bool = False) -> str:
        if value is None:
            return "n/a"
        return f"{value * 100:.2f}%" if percent else f"{value:.3f}"

    lines = [
        "BotTrade benchmark complete",
        f"  run_id:         {outcome.run_id}",
        f"  scenario:       {outcome.scenario.slug}",
        f"  status:         {'published' if outcome.published else 'private'}",
        "  bars_advanced:  "
        + (str(outcome.bars_advanced) if outcome.bars_advanced is not None else "n/a"),
        f"  final_equity:   ${results.final_equity:,.2f}",
        f"  return:         {results.return_pct:+.2f}%",
        f"  sharpe:         {metric(results.sharpe)}",
        f"  sortino:        {metric(results.sortino)}",
        f"  max_drawdown:   {metric(results.max_drawdown, percent=True)}",
        f"  volatility:     {metric(results.volatility, percent=True)}",
        f"  trades:         {results.trade_count}",
        f"  liquidated:     {str(results.liquidated).lower()}",
    ]
    if run_url:
        lines.append(f"  public_url:     {run_url}")
    elif not outcome.published:
        lines.append("  publication:    not requested (use --publish deliberately)")
    return "\n".join(lines)
