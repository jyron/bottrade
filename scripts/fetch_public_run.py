#!/usr/bin/env python3
"""Create a credential-free normalized fixture from a published BotTrade run."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bottrade import BotTradeClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--scenario-version", type=int)
    parser.add_argument("--integration", required=True)
    parser.add_argument("--provider")
    parser.add_argument("--model")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def normalize(args: argparse.Namespace) -> dict[str, Any]:
    with BotTradeClient() as client:
        public = client.get_public_run(args.run_id)

    if public.results is None:
        raise RuntimeError("published run has no computed results")
    agent: dict[str, Any] = {
        "name": public.run.bot_name or "unnamed agent",
        "integration": args.integration,
    }
    if args.provider:
        agent["provider"] = args.provider
    if args.model:
        agent["model"] = args.model

    version = args.scenario_version or public.run.scenario_version
    return {
        "schema_version": 1,
        "run_id": public.run.id,
        "run_url": f"https://bot-trade.org/run/{public.run.id}",
        "scenario": {"slug": args.scenario, "version": version},
        "agent": agent,
        "results": public.results.model_dump(mode="json"),
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }


def main() -> int:
    args = parse_args()
    payload = normalize(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
