"""Command-line interface for public BotTrade discovery and evidence."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from .client import BotTradeClient


def _json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bottrade", description="Inspect BotTrade scenarios and published benchmark evidence."
    )
    parser.add_argument("--api-base", default="https://bot-trade.org")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("scenarios", help="List ready public scenarios.")
    public_run = commands.add_parser("public-run", help="Inspect a published run.")
    public_run.add_argument("run_id")
    badge = commands.add_parser("badge", help="Print Markdown for a verified run badge.")
    badge.add_argument("run_id")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    with BotTradeClient(base_url=args.api_base) as client:
        if args.command == "scenarios":
            _json([scenario.model_dump(mode="json") for scenario in client.list_scenarios()])
        elif args.command == "public-run":
            _json(client.get_public_run(args.run_id).model_dump(mode="json"))
        elif args.command == "badge":
            print(client.badge_markdown(args.run_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
