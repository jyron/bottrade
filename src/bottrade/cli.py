"""Command-line interface for public BotTrade discovery and evidence."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .client import BotTradeClient
from .workflows import format_results, run_buy_and_hold


def _json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bottrade", description="Inspect BotTrade scenarios and published benchmark evidence."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--api-base", default="https://bot-trade.org", help="API origin.")
    commands = parser.add_subparsers(dest="command", required=True)
    scenarios = commands.add_parser("scenarios", help="List ready public scenarios.")
    scenarios.add_argument("--json", action="store_true", help="Emit full machine-readable JSON.")
    public_run = commands.add_parser("public-run", help="Inspect a published run.")
    public_run.add_argument("run_id")
    public_run.add_argument("--json", action="store_true", help="Emit full machine-readable JSON.")
    badge = commands.add_parser("badge", help="Print Markdown for a verified run badge.")
    badge.add_argument("run_id")
    run = commands.add_parser("run", help="Run a complete private buy-and-hold benchmark.")
    run.add_argument("--scenario", default="sandbox-nov-2024", help="Ready scenario slug.")
    run.add_argument("--quantity", type=float, default=10, help="Benchmark-symbol quantity.")
    run.add_argument("--max-bars", type=int, default=10_000, help="Safety cap for steps.")
    run.add_argument("--bot-name", default="BotTrade CLI buy-and-hold", help="Run label.")
    run.add_argument("--output", type=Path, help="Write normalized result JSON.")
    run.add_argument(
        "--publish", action="store_true", help="Make the completed run and trades public."
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    with BotTradeClient(base_url=args.api_base) as client:
        if args.command == "scenarios":
            scenarios = client.list_scenarios()
            if args.json:
                _json([scenario.model_dump(mode="json") for scenario in scenarios])
            else:
                print("SLUG\tSTATUS\tRESOLUTION\tUNIVERSE\tNAME")
                for scenario in scenarios:
                    print(
                        f"{scenario.slug}\t{scenario.status}\t{scenario.bar_resolution}\t"
                        f"{len(scenario.universe)}\t{scenario.name}"
                    )
        elif args.command == "public-run":
            run = client.get_public_run(args.run_id)
            if args.json:
                _json(run.model_dump(mode="json"))
            else:
                print(f"run_id:     {run.run.id}")
                print(f"status:     {run.run.status}")
                print(f"bot_name:   {run.run.bot_name or 'n/a'}")
                result_line = (
                    f"return:     {run.results.return_pct:+.2f}%"
                    if run.results
                    else "return: n/a"
                )
                print(result_line)
                print(f"trades:     {len(run.trades)}")
        elif args.command == "badge":
            print(client.badge_markdown(args.run_id))
        elif args.command == "run":
            outcome = run_buy_and_hold(
                client,
                scenario_slug=args.scenario,
                quantity=args.quantity,
                max_bars=args.max_bars,
                bot_name=args.bot_name,
                publish=args.publish,
                on_started=lambda run: print(f"BotTrade run prepared: {run.id} (private)"),
            )
            url = client.run_url(outcome.run_id) if outcome.published else None
            print(format_results(outcome, run_url=url))
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
