from __future__ import annotations

import json
from typing import cast

import httpx
import pytest

import bottrade
import bottrade.workflows as workflows
from bottrade import (
    AgentInfo,
    AsyncBotTradeClient,
    BenchmarkOutcome,
    BotTradeClient,
    IncompleteRunError,
    MarketObservation,
    Results,
    Run,
    RunSnapshot,
    Scenario,
    StepResult,
    backtest,
    backtest_async,
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


def test_top_level_run_is_a_generic_agent_api(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = BenchmarkOutcome(
        "run-1",
        Scenario.model_validate(SCENARIO),
        Results.model_validate(RESULTS),
        False,
        2,
    )
    call: dict[str, object] = {}

    def fake_backtest(agent: object, scenario: str, **kwargs: object) -> BenchmarkOutcome:
        call["agent"] = agent
        call["scenario"] = scenario
        call.update(kwargs)
        return expected

    monkeypatch.setattr(workflows, "backtest", fake_backtest)

    def agent(_observation: object) -> object:
        return bottrade.hold("waiting")

    result = bottrade.run(agent, "tech-2024-q2", publish=False)

    assert result is expected
    assert result.return_pct == 1.25
    assert result.final_equity == 101250
    assert call["agent"] is agent
    assert call["scenario"] == "tech-2024-q2"
    assert call["publish"] is False


def test_manual_session_observe_submit_step_results() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.done = False
            self.orders: list[dict[str, object]] = []

        def get_scenario(self, _slug: str) -> Scenario:
            return Scenario.model_validate(SCENARIO)

        def start_run(self, _slug: str, **_kwargs: object) -> Run:
            return Run.model_validate(RUN)

        def get_run(self, _run_id: str) -> RunSnapshot:
            status = "completed" if self.done else "active"
            return RunSnapshot(run=Run.model_validate(RUN | {"status": status}))

        def get_market(self, _run_id: str, **_kwargs: object) -> MarketObservation:
            return MarketObservation(
                sim_time="2024-11-01T00:00:00Z",
                bars={"SPY": []},
            )

        def queue_trade(self, _run_id: str, **order: object) -> None:
            self.orders.append(order)

        def step(self, _run_id: str) -> StepResult:
            self.done = True
            return StepResult(
                bars_advanced=1,
                equity=101250,
                cash=50000,
                done=True,
                liquidated=False,
            )

        def get_results(self, _run_id: str) -> Results:
            return Results.model_validate(RESULTS)

    fake = FakeClient()
    info = AgentInfo(name="Manual agent")
    with bottrade.session(
        "sandbox-nov-2024",
        agent_info=info,
        client=cast(BotTradeClient, fake),
    ) as run:
        assert run.active
        assert run.observe().run_id == "run-1"
        run.submit(bottrade.buy("SPY", quantity=3, reasoning="Manual signal"))
        step = run.step()
        assert step.done
        assert run.active is False
        results = run.results()

    assert results.return_pct == 1.25
    assert fake.orders[0]["quantity"] == 3


def test_buy_and_hold_executes_the_complete_private_lifecycle() -> None:
    state = {"steps": 0, "published": False}
    calls: list[tuple[str, str]] = []
    started: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        path = request.url.path
        if request.method == "GET" and path.endswith("/scenarios/sandbox-nov-2024"):
            return httpx.Response(200, json={"scenario": SCENARIO})
        if request.method == "GET" and path.endswith("/market"):
            return httpx.Response(
                200,
                json={
                    "sim_time": "2024-11-01T00:00:00Z",
                    "bars": {
                        "SPY": [
                            {
                                "ts": "2024-11-01T00:00:00Z",
                                "open": 100,
                                "high": 101,
                                "low": 99,
                                "close": 100,
                                "volume": 1000,
                            }
                        ]
                    },
                },
            )
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
            status = "completed" if state["steps"] >= 2 else "active"
            positions = (
                [{"symbol": "SPY", "quantity": 10, "avg_cost": 100}]
                if state["steps"]
                else []
            )
            return httpx.Response(
                200,
                json={"run": RUN | {"status": status}, "positions": positions},
            )
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


def test_custom_agent_controls_every_order_and_provenance() -> None:
    state = {"steps": 0}
    orders: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path.endswith("/scenarios/sandbox-nov-2024"):
            return httpx.Response(200, json={"scenario": SCENARIO})
        if request.method == "POST" and path.endswith("/runs"):
            body = json.loads(request.content)
            assert body["agent_info"]["framework"] == "plain-python"
            return httpx.Response(201, json={"run": RUN | {"agent_info": body["agent_info"]}})
        if request.method == "GET" and path.endswith("/market"):
            return httpx.Response(
                200,
                json={
                    "sim_time": "2024-11-01T00:00:00Z",
                    "bars": {
                        "SPY": [
                            {
                                "ts": "2024-11-01T00:00:00Z",
                                "open": 100,
                                "high": 101,
                                "low": 99,
                                "close": 100,
                                "volume": 1000,
                            }
                        ]
                    },
                },
            )
        if request.method == "GET" and path.endswith("/runs/run-1"):
            status = "completed" if state["steps"] >= 2 else "active"
            return httpx.Response(200, json={"run": RUN | {"status": status}, "positions": []})
        if request.method == "POST" and path.endswith("/trades"):
            body = json.loads(request.content)
            orders.append(body)
            return httpx.Response(201, json={"order": body})
        if request.method == "POST" and path.endswith("/step"):
            state["steps"] += 1
            done = state["steps"] == 2
            return httpx.Response(
                200,
                json={
                    "bars_advanced": 1,
                    "fills": [],
                    "equity": 100000,
                    "cash": 100000,
                    "done": done,
                    "liquidated": False,
                },
            )
        if request.method == "GET" and path.endswith("/results"):
            return httpx.Response(200, json={"results": RESULTS})
        raise AssertionError(f"unexpected request: {request.method} {path}")

    def agent(observation: bottrade.Observation) -> bottrade.Order | bottrade.Decision:
        if observation.step_number == 0:
            return bottrade.buy("SPY", 7, "Custom signal")
        return bottrade.hold("Wait")

    info = AgentInfo(name="Seven share agent", framework="plain-python")
    with BotTradeClient("secret", transport=httpx.MockTransport(handler)) as client:
        result = backtest(agent, agent_info=info, client=client)

    assert result.agent_info == info
    assert result.bars_advanced == 2
    assert len(orders) == 1
    assert orders[0]["symbol"] == "SPY"
    assert orders[0]["quantity"] == 7
    assert orders[0]["reasoning"] == "Custom signal"


@pytest.mark.asyncio
async def test_async_custom_agent_can_hold_to_completion() -> None:
    state = {"done": False}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path.endswith("/scenarios/sandbox-nov-2024"):
            return httpx.Response(200, json={"scenario": SCENARIO})
        if request.method == "POST" and path.endswith("/runs"):
            return httpx.Response(201, json={"run": RUN})
        if request.method == "GET" and path.endswith("/market"):
            return httpx.Response(
                200,
                json={"sim_time": "2024-11-01T00:00:00Z", "bars": {"SPY": []}},
            )
        if request.method == "GET" and path.endswith("/runs/run-1"):
            status = "completed" if state["done"] else "active"
            return httpx.Response(200, json={"run": RUN | {"status": status}})
        if request.method == "POST" and path.endswith("/step"):
            state["done"] = True
            return httpx.Response(
                200,
                json={
                    "bars_advanced": 1,
                    "fills": [],
                    "equity": 100000,
                    "cash": 100000,
                    "done": True,
                    "liquidated": False,
                },
            )
        if request.method == "GET" and path.endswith("/results"):
            return httpx.Response(200, json={"results": RESULTS | {"trade_count": 0}})
        raise AssertionError(f"unexpected request: {request.method} {path}")

    async def agent(_observation: bottrade.Observation) -> bottrade.Decision:
        return bottrade.hold("No order")

    async with AsyncBotTradeClient(
        "secret", transport=httpx.MockTransport(handler)
    ) as client:
        result = await backtest_async(agent, client=client)

    assert result.trade_count == 0
    assert result.bars_advanced == 1


def test_safety_cap_preserves_the_run_id_in_the_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path.endswith("/scenarios/sandbox-nov-2024"):
            return httpx.Response(200, json={"scenario": SCENARIO})
        if request.method == "GET" and path.endswith("/runs/run-1"):
            return httpx.Response(200, json={"run": RUN, "positions": []})
        if request.method == "GET" and path.endswith("/market"):
            return httpx.Response(
                200,
                json={
                    "sim_time": "2024-11-01T00:00:00Z",
                    "bars": {
                        "SPY": [
                            {
                                "ts": "2024-11-01T00:00:00Z",
                                "open": 100,
                                "high": 101,
                                "low": 99,
                                "close": 100,
                                "volume": 1000,
                            }
                        ]
                    },
                },
            )
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
