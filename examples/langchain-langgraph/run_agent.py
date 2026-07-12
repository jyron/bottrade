#!/usr/bin/env python3
"""Run a LangChain/LangGraph agent with BotTrade MCP tools."""

from __future__ import annotations

import argparse
import asyncio
import os

from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model", required=True, help="LangChain model string, including provider."
    )
    parser.add_argument("--scenario", default="sandbox-nov-2024")
    parser.add_argument("--publish", action="store_true")
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    api_key = os.environ.get("BOTTRADE_API_KEY") or os.environ.get("BOT_API_KEY")
    if not api_key:
        raise SystemExit("BOTTRADE_API_KEY is required")

    client = MultiServerMCPClient(
        {
            "bottrade": {
                "transport": "http",
                "url": "https://mcp.bot-trade.org/mcp",
                "headers": {"Authorization": f"Bearer {api_key}"},
            }
        }
    )
    tools = await client.get_tools()
    agent = create_agent(
        args.model,
        tools,
        system_prompt=(
            "Use BotTrade tools to complete one historical-market benchmark. Advance one bar "
            "at a time and report return, Sharpe, Sortino, and drawdown. "
            + (
                "Publication is explicitly authorized for this run."
                if args.publish
                else "Do not call publish_run; the run must remain private."
            )
        ),
    )
    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": f"Run scenario {args.scenario} to completion and show the results.",
                }
            ]
        },
        {"recursion_limit": 300},
    )
    print(result["messages"][-1].content)


def main() -> int:
    asyncio.run(run(parse_args()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
