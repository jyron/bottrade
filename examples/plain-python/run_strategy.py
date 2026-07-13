#!/usr/bin/env python3
"""Backtest a small custom Python agent with BotTrade."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import bottrade


class MomentumAgent:
    """Buy the benchmark once its latest close exceeds the previous close."""

    def __init__(self, quantity: float = 10) -> None:
        self.quantity = quantity

    def decide(self, observation: bottrade.Observation) -> bottrade.Decision | bottrade.Order:
        symbol = observation.scenario.benchmark_symbol or observation.scenario.universe[0]
        bars = observation.bars[symbol]
        if observation.position(symbol):
            return bottrade.hold("Position is open.")
        if len(bars) >= 2 and bars[-1].close > bars[-2].close:
            return bottrade.buy(symbol, self.quantity, "Latest close is above the prior close.")
        return bottrade.hold("Waiting for positive one-bar momentum.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario", default="sandbox-nov-2024", help="Ready BotTrade scenario slug."
    )
    parser.add_argument(
        "--quantity", type=float, default=10, help="Shares or units ordered by this agent."
    )
    parser.add_argument("--lookback", type=int, default=24, help="Visible bars per symbol.")
    parser.add_argument(
        "--max-steps", type=int, default=10_000, help="Safety cap for simulator steps."
    )
    parser.add_argument("--resume-run-id", help="Resume an active run UUID.")
    parser.add_argument("--output", type=Path, help="Write normalized result JSON.")
    parser.add_argument(
        "--publish", action="store_true", help="Publish the completed run and trades."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    info = bottrade.AgentInfo(
        name="Python momentum example",
        framework="python",
        version="1",
        source_url="https://github.com/jyron/bottrade",
        config={"quantity": args.quantity, "lookback": args.lookback},
    )
    result = bottrade.backtest(
        MomentumAgent(args.quantity),
        args.scenario,
        agent_info=info,
        lookback=args.lookback,
        max_steps=args.max_steps,
        publish=args.publish,
        resume_run_id=args.resume_run_id,
        on_started=lambda run: print(f"BotTrade run prepared: {run.id} (private)"),
    )
    print(bottrade.format_results(result))
    if args.output:
        artifact = {
            "run_id": result.run_id,
            "scenario": result.scenario.slug,
            "agent_info": result.agent_info.model_dump(mode="json") if result.agent_info else None,
            "published": result.published,
            "bars_advanced": result.bars_advanced,
            "results": result.results.model_dump(mode="json"),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
