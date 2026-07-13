#!/usr/bin/env python3
"""Minimal buy-and-hold BotTrade benchmark using the typed Python SDK."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bottrade import BotTradeClient, format_results, run_buy_and_hold


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario", default="sandbox-nov-2024", help="Ready BotTrade scenario slug."
    )
    parser.add_argument(
        "--quantity", type=float, default=10, help="Positive benchmark-symbol quantity."
    )
    parser.add_argument(
        "--max-bars", type=int, default=10_000, help="Safety cap for simulator steps."
    )
    parser.add_argument(
        "--bot-name", default="Python buy-and-hold example", help="Run label."
    )
    parser.add_argument("--output", type=Path, help="Write a normalized JSON result artifact.")
    parser.add_argument(
        "--publish", action="store_true", help="Publish only after terminal verification."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    with BotTradeClient.from_env() as client:
        outcome = run_buy_and_hold(
            client,
            scenario_slug=args.scenario,
            quantity=args.quantity,
            max_bars=args.max_bars,
            bot_name=args.bot_name,
            publish=args.publish,
            on_started=lambda run: print(f"BotTrade run prepared: {run.id} (private)"),
        )
        print(
            format_results(
                outcome, run_url=client.run_url(outcome.run_id) if outcome.published else None
            )
        )
        if args.output:
            artifact = {
                "run_id": outcome.run_id,
                "scenario": outcome.scenario.slug,
                "published": outcome.published,
                "bars_advanced": outcome.bars_advanced,
                "results": outcome.results.model_dump(mode="json"),
            }
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
