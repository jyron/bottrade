#!/usr/bin/env python3
"""Run OpenAI, Gemini, or Grok decisions through the BotTrade REST benchmark."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

import httpx

from bottrade import (
    AgentInfo,
    Decision,
    Observation,
    Order,
    RunSnapshot,
    Scenario,
    backtest,
    format_results,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider",
        choices=("openai", "gemini", "grok"),
        required=True,
        help="Provider transport and credential selection.",
    )
    parser.add_argument("--model", required=True, help="Exact provider model identifier.")
    parser.add_argument("--scenario", default="sandbox-nov-2024", help="Scenario slug.")
    parser.add_argument("--bot-name", help="Run label; defaults to provider and model.")
    parser.add_argument("--run-id", help="Resume one existing active run instead of creating one.")
    parser.add_argument(
        "--decide-every", type=int, default=8, help="Request a decision every N bars."
    )
    parser.add_argument(
        "--lookback", type=int, default=24, help="Visible bars per symbol in each prompt."
    )
    parser.add_argument(
        "--max-bars", type=int, default=10_000, help="Safety cap for simulator steps."
    )
    parser.add_argument("--output", type=Path, help="Write normalized result JSON.")
    parser.add_argument(
        "--publish", action="store_true", help="Publish only after completion."
    )
    args = parser.parse_args(argv)
    if args.decide_every < 1 or args.lookback < 1 or args.max_bars < 1:
        parser.error("--decide-every, --lookback, and --max-bars must be at least 1")
    return args


def provider_key(provider: str) -> str:
    variable = {
        "openai": "OPENAI_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "grok": "XAI_API_KEY",
    }[provider]
    value = os.environ.get(variable)
    if not value:
        raise SystemExit(f"{variable} is required")
    return value


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match is None:
            raise
        payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("provider response must be a JSON object")
    return payload


def prompt(scenario: Scenario, snapshot: RunSnapshot, bars: dict[str, Any]) -> str:
    positions = {position.symbol: position.quantity for position in snapshot.positions}
    return "\n".join(
        [
            "You are making one decision in a BotTrade benchmark.",
            'Return JSON only: {"rationale":"...","trades":'
            '[{"symbol":"SPY","side":"buy","quantity":1}]}',
            "Trades may be empty. Side must be buy, sell, short, or cover.",
            f"Scenario: {scenario.slug}",
            f"Universe: {scenario.universe}",
            f"Short enabled: {scenario.short_enabled}",
            f"Cash: {snapshot.run.cash}",
            f"Positions: {positions}",
            f"Visible bars: {json.dumps(bars, default=str)}",
        ]
    )


def decide(provider: str, model: str, key: str, content: str) -> dict[str, Any]:
    if provider in {"openai", "grok"}:
        base = "https://api.openai.com/v1" if provider == "openai" else "https://api.x.ai/v1"
        response = httpx.post(
            base + "/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "Return only valid JSON."},
                    {"role": "user", "content": content},
                ],
                "response_format": {"type": "json_object"},
            },
            timeout=90,
        )
        response.raise_for_status()
        return extract_json(response.json()["choices"][0]["message"]["content"])

    response = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key": key},
        json={
            "contents": [{"role": "user", "parts": [{"text": content}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        },
        timeout=90,
    )
    response.raise_for_status()
    parts = response.json()["candidates"][0]["content"]["parts"]
    return extract_json("".join(part.get("text", "") for part in parts))


class ProviderAgent:
    def __init__(self, provider: str, model: str, key: str) -> None:
        self.provider = provider
        self.model = model
        self.key = key

    def decide(self, observation: Observation) -> Decision:
        payload = decide(
            self.provider,
            self.model,
            self.key,
            prompt(
                observation.scenario,
                observation.snapshot,
                {
                    symbol: [bar.model_dump(mode="json") for bar in values]
                    for symbol, values in observation.bars.items()
                },
            ),
        )
        rationale = str(payload.get("rationale", ""))[:500]
        orders: list[Order] = []
        for trade in payload.get("trades") or []:
            try:
                orders.append(
                    Order(
                        symbol=str(trade["symbol"]).upper(),
                        side=str(trade["side"]).lower(),
                        quantity=float(trade["quantity"]),
                        reasoning=rationale,
                    )
                )
            except (KeyError, TypeError, ValueError) as error:
                print(f"skipped malformed trade {trade!r}: {error}")
        return Decision(orders=orders, reasoning=rationale)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    key = provider_key(args.provider)
    name = args.bot_name or f"{args.provider} {args.model} example"
    info = AgentInfo(
        name=name,
        framework=f"{args.provider}-api",
        model=args.model,
        source_url="https://github.com/jyron/bottrade",
        config={"decide_every": args.decide_every, "lookback": args.lookback},
    )
    result = backtest(
        ProviderAgent(args.provider, args.model, key),
        args.scenario,
        agent_info=info,
        decide_every=args.decide_every,
        lookback=args.lookback,
        max_steps=args.max_bars,
        resume_run_id=args.run_id,
        publish=args.publish,
        on_started=lambda run: print(f"BotTrade run prepared: {run.id} (private)"),
    )
    print(format_results(result))
    if args.output:
        artifact = {
            "run_id": result.run_id,
            "scenario": result.scenario.slug,
            "agent_info": result.agent_info.model_dump(mode="json") if result.agent_info else None,
            "published": result.published,
            "bars_advanced": result.bars_advanced,
            "results": result.results.model_dump(mode="json"),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
