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

from bottrade import BenchmarkOutcome, BotTradeClient, RunSnapshot, Scenario, format_results


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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    key = provider_key(args.provider)
    with BotTradeClient.from_env() as client:
        scenario = client.get_scenario(args.scenario)
        run_id = args.run_id
        if run_id is None:
            run_id = client.start_run(
                scenario.slug, bot_name=args.bot_name or f"{args.provider} {args.model} example"
            ).id
        print(f"BotTrade run prepared: {run_id} (private)")

        for bar_number in range(args.max_bars):
            if bar_number % args.decide_every == 0:
                snapshot = client.get_run(run_id)
                market = client.get_market(run_id, lookback=args.lookback)
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
                            run_id,
                            symbol=str(trade["symbol"]),
                            side=str(trade["side"]),
                            quantity=float(trade["quantity"]),
                            reasoning=rationale,
                        )
                    except (KeyError, TypeError, ValueError) as error:
                        print(f"skipped malformed trade {trade!r}: {error}")

            step = client.step(run_id)
            if step.done or step.liquidated:
                break
        else:
            raise RuntimeError(
                f"run {run_id} did not finish before --max-bars={args.max_bars}; "
                f"resume with --run-id {run_id}"
            )

        results = client.get_results(run_id)
        if args.publish:
            results = client.publish_run(run_id, confirm=True)
        outcome = BenchmarkOutcome(run_id, scenario, results, args.publish, bar_number + 1)
        print(format_results(outcome, run_url=client.run_url(run_id) if args.publish else None))
        if args.output:
            artifact = {
                "run_id": run_id,
                "scenario": scenario.slug,
                "provider": args.provider,
                "model": args.model,
                "published": args.publish,
                "bars_advanced": bar_number + 1,
                "results": results.model_dump(mode="json"),
            }
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
