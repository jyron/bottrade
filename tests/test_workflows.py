from __future__ import annotations

import json

import httpx
import pytest

import bottrade
import bottrade.workflows as workflows
from bottrade import (
    BenchmarkOutcome,
    BotTradeClient,
    IncompleteRunError,
    Results,
    Scenario,
    format_results,
    run_buy_and_hold,
)

SCENARIO = {
    "slug": "sandbox-nov-2024",
    "name": "Election Week Sandbox",
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


def test_top_level_run_is_a_one_call_library_api(monkeypatch: pytest.MonkeyPatch) -> None:
    class OwnedClient:
        def __enter__(self) -> OwnedClient:
            return self

        def __exit__(self, *_: object) -> None:
            return None

    client = OwnedClient()
    expected = BenchmarkOutcome(
        "run-1",
        Scenario.model_validate(SCENARIO),
        Results.model_validate(RESULTS),
        False,
        2,
    )
    call: dict[str, object] = {}

    def fake_workflow(received_client: object, **kwargs: object) -> BenchmarkOutcome:
        call["client"] = received_client
        call.update(kwargs)
        return expected

    monkeypatch.setattr(
        workflows.BotTradeClient,
        "from_env",
        classmethod(lambda _cls, **_kwargs: client),
    )
    monkeypatch.setattr(workflows, "run_buy_and_hold", fake_workflow)

    result = bottrade.run("tech-2024-q2", quantity=3, publish=False)

    assert result is expected
    assert result.return_pct == 1.25
    assert result.final_equity == 101250
    assert call["client"] is client
    assert call["scenario_slug"] == "tech-2024-q2"
    assert call["quantity"] == 3
    assert call["publish"] is False


def test_buy_and_hold_executes_the_complete_private_lifecycle() -> None:
    state = {"steps": 0, "published": False}
    calls: list[tuple[str, str]] = []
    started: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        path = request.url.path
        if request.method == "GET" and path.endswith("/scenarios/sandbox-nov-2024"):
            return httpx.Response(200, json={"scenario": SCENARIO})
        if request.method == "POST" and path.endswith("/runs"):
            return httpx.Response(201, json={"run": RUN})
        if request.method == "POST" and path.endswith("/trades"):
            body = json.loads(request.content)
            assert body["symbol"] == "SPY"
            assert body["quantity"] == 10
            return httpx.Response(201, json={"order": body | {"id": "order-1"}})
        if request.method == "POST" and path.endswith("/step"):
            state["steps"] += 1
            done = state["steps"] == 2
            return httpx.Response(
                200,
                json={
                    "bars_advanced": 1,
                    "fills": [],
                    "equity": 101250,
                    "cash": 50000,
                    "done": done,
                    "liquidated": False,
                },
            )
        if request.method == "GET" and path.endswith("/runs/run-1"):
            return httpx.Response(200, json={"run": RUN | {"status": "completed"}})
        if request.method == "GET" and path.endswith("/results"):
            return httpx.Response(200, json={"results": RESULTS})
        raise AssertionError(f"unexpected request: {request.method} {path}")

    with BotTradeClient("secret", transport=httpx.MockTransport(handler)) as client:
        outcome = run_buy_and_hold(
            client,
            scenario_slug="sandbox-nov-2024",
            on_started=lambda run: started.append(run.id),
        )

    assert outcome.run_id == "run-1"
    assert outcome.published is False
    assert outcome.bars_advanced == 2
    assert started == ["run-1"]
    assert state == {"steps": 2, "published": False}
    assert ("GET", "/api/v1/runs/run-1") in calls
    rendered = format_results(outcome)
    assert "status:         private" in rendered
    assert "max_drawdown:   2.00%" in rendered


def test_safety_cap_preserves_the_run_id_in_the_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET":
            return httpx.Response(200, json={"scenario": SCENARIO})
        if path.endswith("/runs"):
            return httpx.Response(201, json={"run": RUN})
        if path.endswith("/trades"):
            return httpx.Response(
                201,
                json={"order": {"symbol": "SPY", "side": "buy", "quantity": 10}},
            )
        return httpx.Response(
            200,
            json={
                "bars_advanced": 1,
                "fills": [],
                "equity": 100000,
                "cash": 100000,
                "done": False,
                "liquidated": False,
            },
        )

    with (
        BotTradeClient("secret", transport=httpx.MockTransport(handler)) as client,
        pytest.raises(IncompleteRunError, match=r"run_id=run-1"),
    ):
        run_buy_and_hold(client, scenario_slug="sandbox-nov-2024", max_bars=1)
