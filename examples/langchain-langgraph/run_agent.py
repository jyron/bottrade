#!/usr/bin/env python3
"""Run a LangChain/LangGraph agent with BotTrade MCP tools."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

from bottrade import (
    BenchmarkOutcome,
    BotTradeClient,
    IncompleteRunError,
    format_results,
    require_completed_results,
)

BLOCKED_AGENT_TOOLS = {"start_run", "publish_run"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model", required=True, help="LangChain model string, including provider."
    )
    parser.add_argument(
        "--scenario", default="sandbox-nov-2024", help="Scenario for a newly created run."
    )
    parser.add_argument("--bot-name", default="LangChain MCP example", help="Run label.")
    parser.add_argument("--run-id", help="Resume one existing active run instead of creating one.")
    parser.add_argument(
        "--recursion-limit", type=int, default=300, help="LangGraph recursion limit."
    )
    parser.add_argument(
        "--publish", action="store_true", help="Publish only after SDK terminal verification."
    )
    args = parser.parse_args(argv)
    if args.recursion_limit < 1:
        parser.error("--recursion-limit must be at least 1")
    return args


async def run(args: argparse.Namespace) -> None:
    api_key = os.environ.get("BOTTRADE_API_KEY") or os.environ.get("BOT_API_KEY")
    if not api_key:
        raise SystemExit("BOTTRADE_API_KEY is required")

    with BotTradeClient.from_env() as sdk:
        scenario = sdk.get_scenario(args.scenario)
        run_id = args.run_id or sdk.start_run(scenario.slug, bot_name=args.bot_name).id
        print(f"BotTrade run prepared: {run_id} (private)")
        mcp = MultiServerMCPClient(
            {
                "bottrade": {
                    "transport": "http",
                    "url": "https://mcp.bot-trade.org/mcp",
                    "headers": {"Authorization": f"Bearer {api_key}"},
                }
            }
        )
        tools = [tool for tool in await mcp.get_tools() if tool.name not in BLOCKED_AGENT_TOOLS]
        agent = create_agent(
            args.model,
            tools,
            system_prompt=(
                "Use BotTrade tools to operate only the already-created run ID supplied by "
                "the user. Never call start_run or publish_run. Observe state, make one "
                "decision per bar, advance until done or liquidated, then call get_results."
            ),
        )
        result = await agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": f"Complete BotTrade run {run_id}; scenario {scenario.slug}.",
                    }
                ]
            },
            {"recursion_limit": args.recursion_limit},
        )
        print("\nAgent report (untrusted until verification):")
        print(result["messages"][-1].content)
        results = require_completed_results(sdk, run_id)
        if args.publish:
            results = sdk.publish_run(run_id, confirm=True)
        outcome = BenchmarkOutcome(run_id, scenario, results, args.publish, None)
        print("\nSDK verification:")
        print(format_results(outcome, run_url=sdk.run_url(run_id) if args.publish else None))


def main(argv: list[str] | None = None) -> int:
    try:
        asyncio.run(run(parse_args(argv)))
    except IncompleteRunError as error:
        print(f"verification failed: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
