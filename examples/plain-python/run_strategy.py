#!/usr/bin/env python3
"""Minimal buy-and-hold BotTrade benchmark using the typed Python SDK."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bottrade import BotTradeClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="sandbox-nov-2024")
    parser.add_argument("--quantity", type=float, default=10)
    parser.add_argument("--max-bars", type=int, default=10_000)
    parser.add_argument("--output", type=Path, help="Write a normalized JSON result artifact.")
    parser.add_argument("--publish", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with BotTradeClient.from_env() as client:
        scenario = client.get_scenario(args.scenario)
        run = client.start_run(scenario.slug, bot_name="Python buy-and-hold example")
        symbol = scenario.benchmark_symbol or scenario.universe[0]

        client.queue_trade(
            run.id,
            symbol=symbol,
            side="buy",
            quantity=args.quantity,
            reasoning="Starter strategy: buy the scenario benchmark and hold.",
        )

        for _ in range(args.max_bars):
            step = client.step(run.id)
            if step.done or step.liquidated:
                break
        else:
            raise RuntimeError(f"run did not finish before --max-bars={args.max_bars}")

        results = client.get_results(run.id)
        print(f"run:      {run.id}")
        print(f"return:   {results.return_pct:+.2f}%")
        print(f"sharpe:   {results.sharpe}")
        print(f"drawdown: {results.max_drawdown}")

        if args.publish:
            client.publish_run(run.id, confirm=True)
            print(f"published: {client.run_url(run.id)}")
        else:
            print("private:   add --publish only when you want public evidence")
        if args.output:
            artifact = {
                "run_id": run.id,
                "scenario": scenario.slug,
                "published": args.publish,
                "results": results.model_dump(mode="json"),
            }
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
