"""Generic custom-agent backtest workflows."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .agents import (
    AsyncAgent,
    AsyncDecidingAgent,
    DecidingAgent,
    SyncAgent,
    invoke_agent,
    invoke_agent_async,
    resolve_agent_info,
)
from .client import AsyncBotTradeClient, BotTradeClient
from .errors import AgentExecutionError, IncompleteRunError
from .models import AgentInfo, Observation, Results, Run, Scenario

TERMINAL_RUN_STATUSES = frozenset({"completed", "done", "liquidated"})


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """Identity, provenance, and final metrics for one completed backtest."""

    run_id: str
    scenario: Scenario
    results: Results
    published: bool
    bars_advanced: int | None
    agent_info: AgentInfo | None = None

    @property
    def return_pct(self) -> float:
        return self.results.return_pct

    @property
    def final_equity(self) -> float:
        return self.results.final_equity

    @property
    def sharpe(self) -> float | None:
        return self.results.sharpe

    @property
    def sortino(self) -> float | None:
        return self.results.sortino

    @property
    def max_drawdown(self) -> float | None:
        return self.results.max_drawdown

    @property
    def trade_count(self) -> int:
        return self.results.trade_count


BenchmarkOutcome = BacktestResult


def require_completed_results(client: BotTradeClient, run_id: str) -> Results:
    snapshot = client.get_run(run_id)
    if snapshot.run.status.lower() not in TERMINAL_RUN_STATUSES:
        raise IncompleteRunError(
            f"Run {run_id} is {snapshot.run.status!r}. Resume with run_id={run_id}."
        )
    return client.get_results(run_id)


async def require_completed_results_async(
    client: AsyncBotTradeClient, run_id: str
) -> Results:
    snapshot = await client.get_run(run_id)
    if snapshot.run.status.lower() not in TERMINAL_RUN_STATUSES:
        raise IncompleteRunError(
            f"Run {run_id} is {snapshot.run.status!r}. Resume with run_id={run_id}."
        )
    return await client.get_results(run_id)


def _validate_controls(lookback: int, decide_every: int, max_steps: int) -> None:
    if lookback < 1 or decide_every < 1 or max_steps < 1:
        raise ValueError("lookback, decide_every, and max_steps must be at least one")


def backtest(
    agent: SyncAgent | DecidingAgent,
    scenario: str = "sandbox-nov-2024",
    *,
    agent_info: AgentInfo | None = None,
    lookback: int = 50,
    decide_every: int = 1,
    max_steps: int = 10_000,
    publish: bool = False,
    resume_run_id: str | None = None,
    api_key: str | None = None,
    timeout: float = 45.0,
    client: BotTradeClient | None = None,
    on_started: Callable[[Run], None] | None = None,
) -> BacktestResult:
    """Backtest any synchronous custom agent to completion."""

    _validate_controls(lookback, decide_every, max_steps)
    info = resolve_agent_info(agent, agent_info)
    owned_client = client is None
    sdk = client or (
        BotTradeClient(api_key, timeout=timeout)
        if api_key is not None
        else BotTradeClient.from_env(timeout=timeout)
    )
    try:
        scenario_model = sdk.get_scenario(scenario)
        if resume_run_id:
            run_id = resume_run_id
        else:
            created = sdk.start_run(
                scenario_model.slug,
                bot_name=info.name,
                agent_info=info,
            )
            run_id = created.id
            if on_started:
                on_started(created)

        bars_advanced = 0
        snapshot = sdk.get_run(run_id)
        if snapshot.run.status.lower() not in TERMINAL_RUN_STATUSES:
            for step_number in range(max_steps):
                if step_number % decide_every == 0:
                    market = sdk.get_market(
                        run_id,
                        symbols=scenario_model.universe,
                        lookback=lookback,
                    )
                    observation = Observation(
                        scenario=scenario_model,
                        snapshot=snapshot,
                        market=market,
                        step_number=step_number,
                    )
                    try:
                        decision = invoke_agent(agent, observation)
                    except Exception as error:
                        raise AgentExecutionError(run_id, step_number, error) from error
                    for order in decision.orders:
                        sdk.queue_trade(
                            run_id,
                            symbol=order.symbol,
                            side=order.side,
                            quantity=order.quantity,
                            reasoning=order.reasoning or decision.reasoning,
                        )

                step = sdk.step(run_id)
                bars_advanced += step.bars_advanced
                if step.done or step.liquidated:
                    break
                snapshot = sdk.get_run(run_id)
            else:
                raise IncompleteRunError(
                    f"Run {run_id} reached max_steps={max_steps}. Resume with run_id={run_id}."
                )

        results = require_completed_results(sdk, run_id)
        if publish:
            results = sdk.publish_run(run_id, confirm=True)
        return BacktestResult(
            run_id,
            scenario_model,
            results,
            publish,
            bars_advanced,
            info,
        )
    finally:
        if owned_client:
            sdk.close()


async def backtest_async(
    agent: SyncAgent | AsyncAgent | DecidingAgent | AsyncDecidingAgent,
    scenario: str = "sandbox-nov-2024",
    *,
    agent_info: AgentInfo | None = None,
    lookback: int = 50,
    decide_every: int = 1,
    max_steps: int = 10_000,
    publish: bool = False,
    resume_run_id: str | None = None,
    api_key: str | None = None,
    timeout: float = 45.0,
    client: AsyncBotTradeClient | None = None,
    on_started: Callable[[Run], Any] | None = None,
) -> BacktestResult:
    """Backtest any synchronous or asynchronous custom agent to completion."""

    _validate_controls(lookback, decide_every, max_steps)
    info = resolve_agent_info(agent, agent_info)
    owned_client = client is None
    sdk = client or (
        AsyncBotTradeClient(api_key, timeout=timeout)
        if api_key is not None
        else AsyncBotTradeClient.from_env(timeout=timeout)
    )
    try:
        scenario_model = await sdk.get_scenario(scenario)
        if resume_run_id:
            run_id = resume_run_id
        else:
            created = await sdk.start_run(
                scenario_model.slug,
                bot_name=info.name,
                agent_info=info,
            )
            run_id = created.id
            if on_started:
                on_started(created)

        bars_advanced = 0
        snapshot = await sdk.get_run(run_id)
        if snapshot.run.status.lower() not in TERMINAL_RUN_STATUSES:
            for step_number in range(max_steps):
                if step_number % decide_every == 0:
                    market = await sdk.get_market(
                        run_id,
                        symbols=scenario_model.universe,
                        lookback=lookback,
                    )
                    observation = Observation(
                        scenario=scenario_model,
                        snapshot=snapshot,
                        market=market,
                        step_number=step_number,
                    )
                    try:
                        decision = await invoke_agent_async(agent, observation)
                    except Exception as error:
                        raise AgentExecutionError(run_id, step_number, error) from error
                    for order in decision.orders:
                        await sdk.queue_trade(
                            run_id,
                            symbol=order.symbol,
                            side=order.side,
                            quantity=order.quantity,
                            reasoning=order.reasoning or decision.reasoning,
                        )

                step = await sdk.step(run_id)
                bars_advanced += step.bars_advanced
                if step.done or step.liquidated:
                    break
                snapshot = await sdk.get_run(run_id)
            else:
                raise IncompleteRunError(
                    f"Run {run_id} reached max_steps={max_steps}. Resume with run_id={run_id}."
                )

        results = await require_completed_results_async(sdk, run_id)
        if publish:
            results = await sdk.publish_run(run_id, confirm=True)
        return BacktestResult(
            run_id,
            scenario_model,
            results,
            publish,
            bars_advanced,
            info,
        )
    finally:
        if owned_client:
            await sdk.aclose()


def run(
    agent: SyncAgent | DecidingAgent,
    scenario: str = "sandbox-nov-2024",
    **kwargs: Any,
) -> BacktestResult:
    """Short alias for :func:`backtest`."""

    return backtest(agent, scenario, **kwargs)


def run_buy_and_hold(
    client: BotTradeClient,
    *,
    scenario_slug: str,
    quantity: float = 10,
    max_bars: int = 10_000,
    bot_name: str = "Buy and hold",
    publish: bool = False,
    on_started: Callable[[Run], None] | None = None,
) -> BacktestResult:
    """Compatibility wrapper for the explicit buy-and-hold reference agent."""

    from .strategies import buy_and_hold

    return backtest(
        buy_and_hold(quantity),
        scenario_slug,
        agent_info=AgentInfo(
            name=bot_name,
            framework="bottrade",
            version="1",
            config={"quantity": quantity},
        ),
        max_steps=max_bars,
        publish=publish,
        client=client,
        on_started=on_started,
    )


def format_results(outcome: BacktestResult, *, run_url: str | None = None) -> str:
    results = outcome.results

    def metric(value: float | None, *, percent: bool = False) -> str:
        if value is None:
            return "n/a"
        return f"{value * 100:.2f}%" if percent else f"{value:.3f}"

    lines = [
        "BotTrade backtest complete",
        f"  run_id:         {outcome.run_id}",
        f"  agent:          {outcome.agent_info.name if outcome.agent_info else 'n/a'}",
        f"  scenario:       {outcome.scenario.slug}",
        f"  status:         {'published' if outcome.published else 'private'}",
        "  bars_advanced:  "
        + (str(outcome.bars_advanced) if outcome.bars_advanced is not None else "n/a"),
        f"  final_equity:   ${results.final_equity:,.2f}",
        f"  return:         {results.return_pct:+.2f}%",
        f"  sharpe:         {metric(results.sharpe)}",
        f"  sortino:        {metric(results.sortino)}",
        f"  max_drawdown:   {metric(results.max_drawdown, percent=True)}",
        f"  volatility:     {metric(results.volatility, percent=True)}",
        f"  trades:         {results.trade_count}",
        f"  liquidated:     {str(results.liquidated).lower()}",
    ]
    if run_url:
        lines.append(f"  public_url:     {run_url}")
    return "\n".join(lines)
