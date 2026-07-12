#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "examples" / "ai-hedge-fund" / "adapter.py"
SPEC = importlib.util.spec_from_file_location("ai_hedge_fund_adapter", SCRIPT)
assert SPEC and SPEC.loader
adapter = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = adapter
SPEC.loader.exec_module(adapter)


def make_bars(close: float = 100.0, count: int = 130) -> list[dict]:
    return [
        {
            "ts": f"2024-01-{(index // 24) + 1:02d}T{index % 24:02d}:00:00Z",
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 1_000 + index,
        }
        for index in range(count)
    ]


def snapshot() -> dict:
    return {
        "run": {
            "cash": 9_000.0,
            "starting_cash": 10_000.0,
            "sim_time": "2024-05-15T12:00:00Z",
        },
        "positions": [
            {"symbol": "AAPL", "quantity": 10.0, "avg_cost": 100.0},
            {"symbol": "MSFT", "quantity": -5.0, "avg_cost": 200.0},
        ],
        "last_equity": {"equity": 10_250.0},
    }


class AsOfStrategyTests(unittest.TestCase):
    def test_passes_the_current_scenario_date_and_portfolio_to_the_upstream_runner(self) -> None:
        calls: list[dict] = []

        def runner(**kwargs: object) -> dict:
            calls.append(kwargs)
            return {"decisions": {"AAPL": {"action": "buy", "quantity": 3}}}

        strategy = adapter.AsOfStrategy(
            history_days=180,
            model_name="test-model",
            model_provider="Test Provider",
            selected_analysts=["technical_analyst"],
            runner=runner,
        )
        decisions = strategy.decide(
            snapshot(),
            {"universe": ["AAPL", "MSFT"], "leverage_cap": 2.0},
        )

        self.assertEqual(decisions["AAPL"]["action"], "buy")
        self.assertEqual(calls[0]["end_date"], "2024-05-15")
        self.assertEqual(calls[0]["start_date"], "2023-11-17")
        portfolio = calls[0]["portfolio"]
        self.assertEqual(portfolio["cash"], 9_000.0)
        self.assertEqual(portfolio["equity"], 10_250.0)
        self.assertEqual(portfolio["positions"]["AAPL"]["long"], 10.0)
        self.assertEqual(portfolio["positions"]["MSFT"]["short"], 5.0)
        self.assertEqual(portfolio["margin_requirement"], 0.5)

    def test_external_orders_are_clamped_to_positions_and_shorting_rules(self) -> None:
        positions = {"AAPL": 4.0, "MSFT": -3.0}
        sell = adapter.order_from_decision(
            "AAPL",
            {"action": "sell", "quantity": 10, "reasoning": "reduce"},
            positions,
            short_enabled=True,
        )
        cover = adapter.order_from_decision(
            "MSFT", {"action": "cover", "quantity": 10}, positions, short_enabled=True
        )
        short = adapter.order_from_decision(
            "AAPL", {"action": "short", "quantity": 2}, positions, short_enabled=False
        )

        self.assertEqual(sell["quantity"], 4.0)
        self.assertEqual(cover["quantity"], 3.0)
        self.assertIsNone(short)


class FakeTechnicalModule:
    def __init__(self) -> None:
        self.frames_seen = 0

    def _signal(self, frame: object) -> dict:
        self.frames_seen += 1
        self.last_columns = list(frame.columns)
        return {"signal": "bullish", "confidence": 0.5, "metrics": {}}

    calculate_trend_signals = _signal
    calculate_mean_reversion_signals = _signal
    calculate_momentum_signals = _signal
    calculate_volatility_signals = _signal
    calculate_stat_arb_signals = _signal

    @staticmethod
    def weighted_signal_combination(_components: dict, _weights: dict) -> dict:
        return {"signal": "bullish", "confidence": 0.7}


class TechnicalStrategyTests(unittest.TestCase):
    def test_uses_bottrade_bars_for_every_technical_component(self) -> None:
        upstream = FakeTechnicalModule()
        strategy = adapter.TechnicalStrategy(upstream)
        signals = strategy.analyze({"AAPL": make_bars()})

        self.assertEqual(upstream.frames_seen, 5)
        self.assertEqual(upstream.last_columns, ["open", "high", "low", "close", "volume"])
        self.assertEqual(signals["AAPL"].direction, "bullish")
        self.assertEqual(signals["AAPL"].confidence, 0.7)
        self.assertEqual(len(signals["AAPL"].components), 5)

    def test_targets_follow_the_position_limit_and_reverse_in_two_decisions(self) -> None:
        signals = {
            "AAPL": adapter.Signal("AAPL", "bullish", 0.8),
            "MSFT": adapter.Signal("MSFT", "bullish", 0.6),
            "NVDA": adapter.Signal("NVDA", "bullish", 0.9),
        }
        targets = adapter.technical_targets(
            signals,
            {},
            {"AAPL": 100.0, "MSFT": 100.0, "NVDA": 100.0},
            10_000.0,
            short_enabled=False,
            max_positions=2,
            gross_exposure=0.8,
            min_confidence=0.15,
        )
        self.assertEqual(targets, {"NVDA": 40.0, "AAPL": 40.0})

        reversal = adapter.orders_for_targets(
            {"AAPL": 15.0},
            {"AAPL": -20.0},
            {"AAPL": adapter.Signal("AAPL", "bearish", 0.9)},
        )
        self.assertEqual(reversal[0]["side"], "sell")
        self.assertEqual(reversal[0]["quantity"], 15.0)

    def test_trade_reason_exposes_target_and_component_decisions(self) -> None:
        signal = adapter.Signal(
            "AAPL",
            "bullish",
            0.64,
            (("trend", "bullish", 0.8), ("momentum", "neutral", 0.5)),
        )

        reason = adapter.technical_decision_reason(signal, 10.0, 25.0)

        self.assertIn("bullish 64%", reason)
        self.assertIn("position 10 -> target 25", reason)
        self.assertIn("trend=bullish 80%", reason)
        self.assertIn("momentum=neutral 50%", reason)


class FakeClient:
    def __init__(self) -> None:
        self.orders: list[dict] = []
        self.steps = 0
        self.starts = 0
        self.was_published = False

    def scenario(self, slug: str) -> dict:
        return {
            "slug": slug,
            "name": "Adapter test",
            "universe": ["AAPL"],
            "short_enabled": False,
            "leverage_cap": 1.0,
        }

    def start_run(self, _slug: str, _bot_name: str) -> dict:
        self.starts += 1
        return {"id": "test-run"}

    def snapshot(self, _run_id: str) -> dict:
        return {
            "run": {
                "cash": 10_000.0,
                "starting_cash": 10_000.0,
                "sim_time": "2024-05-15T12:00:00Z",
            },
            "positions": [],
            "last_equity": {"equity": 10_000.0},
        }

    def market(self, _run_id: str, _symbols: list[str], _lookback: int) -> dict:
        return {"bars": {"AAPL": make_bars()}}

    def queue_trade(self, _run_id: str, **order: object) -> None:
        self.orders.append(order)

    def step(self, _run_id: str) -> dict:
        self.steps += 1
        return {"done": self.steps == 2, "liquidated": False}

    def results(self, _run_id: str) -> dict:
        return {
            "return_pct": 1.25,
            "final_equity": 10_125.0,
            "trade_count": len(self.orders),
            "liquidated": False,
        }

    def publish(self, _run_id: str) -> None:
        self.was_published = True


class AdapterLifecycleTests(unittest.TestCase):
    def test_as_of_run_queues_orders_finishes_and_publishes(self) -> None:
        def runner(**_kwargs: object) -> dict:
            return {"decisions": {"AAPL": {"action": "buy", "quantity": 10, "reasoning": "signal"}}}

        client = FakeClient()
        strategy = adapter.AsOfStrategy(
            history_days=180,
            model_name="test",
            model_provider="test",
            selected_analysts=[],
            runner=runner,
        )
        config = adapter.RunConfig(
            scenario_slug="adapter-test",
            bot_name="ai-hedge-fund as-of",
            mode="as-of",
            decide_every=2,
            lookback=180,
            max_bars=10,
            max_positions=4,
            gross_exposure=0.8,
            min_confidence=0.15,
            publish=True,
        )

        run, results = adapter.execute_benchmark(client, config, as_of_strategy=strategy)

        self.assertEqual(run["id"], "test-run")
        self.assertEqual(results["final_equity"], 10_125.0)
        self.assertTrue(client.was_published)
        self.assertEqual(client.orders[0]["symbol"], "AAPL")
        self.assertEqual(client.orders[0]["side"], "buy")
        self.assertEqual(client.orders[0]["quantity"], 10.0)

    def test_resume_uses_the_existing_run(self) -> None:
        client = FakeClient()
        config = adapter.RunConfig(
            scenario_slug="adapter-test",
            bot_name="ai-hedge-fund technical",
            mode="technical",
            decide_every=2,
            lookback=180,
            max_bars=10,
            max_positions=4,
            gross_exposure=0.8,
            min_confidence=0.15,
            publish=False,
            run_id="test-run",
        )

        adapter.execute_benchmark(
            client, config, technical_strategy=adapter.TechnicalStrategy(FakeTechnicalModule())
        )

        self.assertEqual(client.starts, 0)


if __name__ == "__main__":
    unittest.main()
