"""Command-line interface for public BotTrade discovery and evidence."""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import __version__
from .client import BotTradeClient
from .models import AgentInfo
from .workflows import backtest, format_results


def _json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def _load_agent(spec: str) -> Any:
    module_name, separator, attribute_name = spec.partition(":")
    if not separator or not module_name or not attribute_name:
        raise ValueError("agent must use module:attribute syntax, for example my_agent:decide")
    value = getattr(importlib.import_module(module_name), attribute_name)
    return value() if inspect.isclass(value) else value


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
    command = commands.add_parser("backtest", help="Backtest a Python agent to completion.")
    command.add_argument("agent", help="Import path in module:attribute form.")
    command.add_argument("--scenario", default="sandbox-nov-2024", help="Ready scenario slug.")
    command.add_argument("--lookback", type=int, default=50, help="Visible bars per symbol.")
    command.add_argument(
        "--decide-every", type=int, default=1, help="Call the agent every N bars."
    )
    command.add_argument("--max-steps", type=int, default=10_000, help="Safety cap for steps.")
    command.add_argument("--resume-run-id", help="Resume an active run UUID.")
    command.add_argument("--name", help="Agent name stored with the run.")
    command.add_argument("--framework", default="python", help="Agent framework.")
    command.add_argument("--model", help="Model identifier.")
    command.add_argument("--agent-version", help="Agent version.")
    command.add_argument("--source-url", help="Source repository URL.")
    command.add_argument("--source-revision", help="Commit or immutable source revision.")
    command.add_argument("--output", type=Path, help="Write normalized result JSON.")
    command.add_argument(
        "--publish", action="store_true", help="Make the completed run and trades public."
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    api_key = os.getenv("BOTTRADE_API_KEY") or os.getenv("BOT_API_KEY")
    with BotTradeClient(api_key, base_url=args.api_base) as client:
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
        elif args.command == "backtest":
            agent = _load_agent(args.agent)
            info = (
                AgentInfo(
                    name=args.name,
                    framework=args.framework,
                    model=args.model,
                    version=args.agent_version,
                    source_url=args.source_url,
                    source_revision=args.source_revision,
                )
                if args.name
                else None
            )
            outcome = backtest(
                agent,
                args.scenario,
                agent_info=info,
                lookback=args.lookback,
                decide_every=args.decide_every,
                max_steps=args.max_steps,
                publish=args.publish,
                resume_run_id=args.resume_run_id,
                client=client,
                on_started=lambda run: print(f"BotTrade run prepared: {run.id} (private)"),
            )
            url = client.run_url(outcome.run_id) if outcome.published else None
            print(format_results(outcome, run_url=url))
            if args.output:
                artifact = {
                    "run_id": outcome.run_id,
                    "scenario": outcome.scenario.slug,
                    "agent_info": (
                        outcome.agent_info.model_dump(mode="json") if outcome.agent_info else None
                    ),
                    "published": outcome.published,
                    "bars_advanced": outcome.bars_advanced,
                    "results": outcome.results.model_dump(mode="json"),
                }
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
