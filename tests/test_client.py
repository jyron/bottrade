from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from bottrade import (
    APIError,
    AsyncBotTradeClient,
    AuthenticationRequired,
    BotTradeClient,
    PublicationConfirmationRequired,
    RetryPolicy,
)

SCENARIO = {
    "slug": "sandbox-nov-2024",
    "name": "Election Week Sandbox",
    "description": "A short integration scenario.",
    "status": "ready",
    "universe": ["SPY"],
    "starting_cash": 100000,
    "leverage_cap": 1,
    "short_enabled": False,
    "bar_resolution": "1Hour",
    "start_ts": "2024-11-01T00:00:00Z",
    "end_ts": "2024-11-08T00:00:00Z",
    "benchmark_symbol": "SPY",
}

RUN = {
    "id": "run-1",
    "status": "active",
    "cash": 100000,
    "starting_cash": 100000,
    "sim_time": "2024-11-01T00:00:00Z",
}

RESULTS = {
    "final_equity": 101250,
    "return_pct": 1.25,
    "sharpe": 1.1,
    "sortino": 1.4,
    "max_drawdown": 0.02,
    "volatility": 0.1,
    "trade_count": 1,
    "liquidated": False,
}


def transport(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def test_public_discovery_does_not_send_auth() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"scenarios": [SCENARIO]})

    with BotTradeClient(transport=transport(handler)) as client:
        scenarios = client.list_scenarios()

    assert scenarios[0].slug == "sandbox-nov-2024"
    assert scenarios[0].start_ts.year == 2024


def test_protected_operation_requires_a_key_before_network_io() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    with (
        BotTradeClient(transport=transport(handler)) as client,
        pytest.raises(AuthenticationRequired),
    ):
        client.start_run("sandbox-nov-2024")

    assert calls == 0


def test_transient_get_is_retried_and_api_error_is_structured() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, json={"error": "edge unavailable"})
        if request.url.path.endswith("missing"):
            return httpx.Response(404, json={"detail": "no such scenario"})
        return httpx.Response(200, json={"scenario": SCENARIO})

    policy = RetryPolicy(attempts=2, base_delay_seconds=0)
    with BotTradeClient(transport=transport(handler), retry_policy=policy) as client:
        assert client.get_scenario("sandbox-nov-2024").status == "ready"
        with pytest.raises(APIError) as raised:
            client.get_scenario("missing")

    assert calls == 3
    assert raised.value.status_code == 404
    assert raised.value.message == "no such scenario"
    assert raised.value.method == "GET"


def test_trade_and_step_generate_distinct_idempotency_keys() -> None:
    keys: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        keys.append(payload["idempotency_key"])
        if request.url.path.endswith("/trades"):
            return httpx.Response(
                201,
                json={"order": {"id": "order-1", "symbol": "SPY", "side": "buy", "quantity": 1}},
            )
        return httpx.Response(
            200,
            json={
                "bars_advanced": 1,
                "new_sim_time": "2024-11-01T01:00:00Z",
                "fills": [],
                "equity": 100000,
                "cash": 100000,
                "done": False,
                "liquidated": False,
            },
        )

    with BotTradeClient("secret", transport=transport(handler)) as client:
        order = client.queue_trade("run-1", symbol="spy", side="BUY", quantity=1)
        step = client.step("run-1")

    assert order.symbol == "SPY"
    assert step.bars_advanced == 1
    assert len(set(keys)) == 2


def test_publication_requires_explicit_confirmation() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"published": True, "results": RESULTS})

    with BotTradeClient("secret", transport=transport(handler)) as client:
        with pytest.raises(PublicationConfirmationRequired):
            client.publish_run("run-1")
        results = client.publish_run("run-1", confirm=True)

    assert calls == 1
    assert results.return_pct == 1.25


@pytest.mark.asyncio
async def test_async_client_matches_sync_contract() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer secret"
        return httpx.Response(201, json={"run": RUN})

    async with AsyncBotTradeClient("secret", transport=httpx.MockTransport(handler)) as client:
        run = await client.start_run("sandbox-nov-2024", bot_name="async example")

    assert run.id == "run-1"
    assert run.bot_name is None


def test_badge_helpers_are_stable() -> None:
    with BotTradeClient(base_url="https://bot-trade.org/") as client:
        assert client.run_url("abc") == "https://bot-trade.org/run/abc"
        assert client.badge_url("abc").endswith("/run/abc/badge.svg")
        assert client.badge_markdown("abc") == (
            "[![Tested on BotTrade](https://bot-trade.org/run/abc/badge.svg)]"
            "(https://bot-trade.org/run/abc)"
        )
