#!/usr/bin/env python3
"""Run an OpenAI Agents SDK agent against BotTrade through hosted MCP."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any

from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp

from bottrade import (
    BenchmarkOutcome,
    BotTradeClient,
    IncompleteRunError,
    format_results,
    require_completed_results,
)

BLOCKED_AGENT_TOOLS = ["start_run", "publish_run"]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario", default="sandbox-nov-2024", help="Scenario for a newly created run."
    )
    parser.add_argument("--model", help="Optional OpenAI model override.")
    parser.add_argument("--bot-name", default="OpenAI Agents MCP example", help="Run label.")
    parser.add_argument("--run-id", help="Resume one existing active run instead of creating one.")
    parser.add_argument("--max-turns", type=int, default=250, help="Agents SDK turn limit.")
    parser.add_argument(
        "--publish", action="store_true", help="Publish only after SDK terminal verification."
    )
    args = parser.parse_args(argv)
    if args.max_turns < 1:
        parser.error("--max-turns must be at least 1")
    return args


async def run(args: argparse.Namespace) -> None:
    api_key = os.environ.get("BOTTRADE_API_KEY") or os.environ.get("BOT_API_KEY")
    if not api_key:
        raise SystemExit("BOTTRADE_API_KEY is required")

    with BotTradeClient.from_env() as client:
        scenario = client.get_scenario(args.scenario)
        run_id = args.run_id or client.start_run(scenario.slug, bot_name=args.bot_name).id
        print(f"BotTrade run prepared: {run_id} (private)")
        async with MCPServerStreamableHttp(
            name="BotTrade",
            params={
                "url": "https://mcp.bot-trade.org/mcp",
                "headers": {"Authorization": f"Bearer {api_key}"},
                "timeout": 45,
            },
            cache_tools_list=True,
            max_retry_attempts=3,
            tool_filter={"blocked_tool_names": BLOCKED_AGENT_TOOLS},
        ) as server:
            instructions = (
                "Use BotTrade MCP tools to operate only the already-created run ID supplied "
                "by the user. Never call start_run or publish_run. Observe state, make one "
                "decision per bar, advance until done or liquidated, then call get_results."
            )
            agent_kwargs: dict[str, Any] = {
                "name": "BotTrade benchmark agent",
                "instructions": instructions,
                "mcp_servers": [server],
            }
            if args.model:
                agent_kwargs["model"] = args.model
            agent = Agent(**agent_kwargs)
            result = await Runner.run(
                agent,
                f"Complete BotTrade run {run_id}. It uses scenario {scenario.slug}.",
                max_turns=args.max_turns,
            )
            print("\nAgent report (untrusted until verification):")
            print(result.final_output)

        results = require_completed_results(client, run_id)
        if args.publish:
            results = client.publish_run(run_id, confirm=True)
        outcome = BenchmarkOutcome(run_id, scenario, results, args.publish, None)
        print("\nSDK verification:")
        print(format_results(outcome, run_url=client.run_url(run_id) if args.publish else None))


def main(argv: list[str] | None = None) -> int:
    try:
        asyncio.run(run(parse_args(argv)))
    except IncompleteRunError as error:
        print(f"verification failed: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
