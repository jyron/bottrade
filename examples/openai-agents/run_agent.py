#!/usr/bin/env python3
"""Run an OpenAI Agents SDK agent against BotTrade through hosted MCP."""

from __future__ import annotations

import argparse
import asyncio
import os
from typing import Any

from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="sandbox-nov-2024")
    parser.add_argument("--model", help="Optional OpenAI model override.")
    parser.add_argument("--publish", action="store_true")
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    api_key = os.environ.get("BOTTRADE_API_KEY") or os.environ.get("BOT_API_KEY")
    if not api_key:
        raise SystemExit("BOTTRADE_API_KEY is required")

    async with MCPServerStreamableHttp(
        name="BotTrade",
        params={
            "url": "https://mcp.bot-trade.org/mcp",
            "headers": {"Authorization": f"Bearer {api_key}"},
            "timeout": 45,
        },
        cache_tools_list=True,
        max_retry_attempts=3,
    ) as server:
        instructions = (
            "You evaluate trading agents with BotTrade. Use the BotTrade MCP tools to run "
            "the requested scenario to completion. Start with scenario discovery, make one "
            "decision per bar, stop when done or liquidated, and report risk-aware results. "
            + (
                "The user explicitly requested publication; publish the completed run."
                if args.publish
                else "Keep the run private. Never call publish_run."
            )
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
            f"Run the {args.scenario} BotTrade scenario to completion and show the final results.",
            max_turns=250,
        )
        print(result.final_output)


def main() -> int:
    asyncio.run(run(parse_args()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
