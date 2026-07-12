#!/usr/bin/env python3
"""Run OpenAI, Gemini, or Grok decisions through the BotTrade REST benchmark."""

from __future__ import annotations

import argparse
import json
import os
import re
from typing import Any

import httpx

from bottrade import BotTradeClient, RunSnapshot, Scenario


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("openai", "gemini", "grok"), required=True)
    parser.add_argument("--model", required=True, help="Exact provider model identifier.")
    parser.add_argument("--scenario", default="sandbox-nov-2024")
    parser.add_argument("--decide-every", type=int, default=8)
    parser.add_argument("--lookback", type=int, default=24)
    parser.add_argument("--max-bars", type=int, default=10_000)
    parser.add_argument("--publish", action="store_true")
    return parser.parse_args()


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


def main() -> int:
    args = parse_args()
    key = provider_key(args.provider)
    with BotTradeClient.from_env() as client:
        scenario = client.get_scenario(args.scenario)
        run = client.start_run(
            scenario.slug, bot_name=f"{args.provider} {args.model} public example"
        )

        for bar_number in range(args.max_bars):
            if bar_number % args.decide_every == 0:
                snapshot = client.get_run(run.id)
                market = client.get_market(run.id, lookback=args.lookback)
                decision = decide(
                    args.provider,
                    args.model,
                    key,
                    prompt(
                        scenario,
                        snapshot,
                        {
                            symbol: [bar.model_dump(mode="json") for bar in values]
                            for symbol, values in market.bars.items()
                        },
                    ),
                )
                rationale = str(decision.get("rationale", ""))[:500]
                for trade in decision.get("trades") or []:
                    try:
                        client.queue_trade(
                            run.id,
                            symbol=str(trade["symbol"]),
                            side=str(trade["side"]),
                            quantity=float(trade["quantity"]),
                            reasoning=rationale,
                        )
                    except (KeyError, TypeError, ValueError) as error:
                        print(f"skipped malformed trade {trade!r}: {error}")

            step = client.step(run.id)
            if step.done or step.liquidated:
                break
        else:
            raise RuntimeError(f"run did not finish before --max-bars={args.max_bars}")

        results = client.get_results(run.id)
        print(results.model_dump_json(indent=2))
        if args.publish:
            client.publish_run(run.id, confirm=True)
            print(client.run_url(run.id))
        else:
            print("Run remains private. Add --publish only for deliberate public evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
