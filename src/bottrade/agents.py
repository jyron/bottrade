"""Custom-agent input, output, and normalization helpers."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Protocol, TypeAlias, cast

from .models import AgentInfo, Decision, Observation, Order

DecisionLike: TypeAlias = Decision | Order | Sequence[Order] | None
SyncAgent: TypeAlias = Callable[[Observation], DecisionLike]
AsyncAgent: TypeAlias = Callable[[Observation], Awaitable[DecisionLike]]


class DecidingAgent(Protocol):
    """Stateful agent interface accepted by :func:`bottrade.backtest`."""

    def decide(self, observation: Observation) -> DecisionLike: ...


class AsyncDecidingAgent(Protocol):
    """Stateful async interface accepted by :func:`bottrade.backtest_async`."""

    async def decide(self, observation: Observation) -> DecisionLike: ...


def buy(symbol: str, quantity: float, reasoning: str | None = None) -> Order:
    return Order(symbol=symbol.upper(), side="buy", quantity=quantity, reasoning=reasoning)


def sell(symbol: str, quantity: float, reasoning: str | None = None) -> Order:
    return Order(symbol=symbol.upper(), side="sell", quantity=quantity, reasoning=reasoning)


def short(symbol: str, quantity: float, reasoning: str | None = None) -> Order:
    return Order(symbol=symbol.upper(), side="short", quantity=quantity, reasoning=reasoning)


def cover(symbol: str, quantity: float, reasoning: str | None = None) -> Order:
    return Order(symbol=symbol.upper(), side="cover", quantity=quantity, reasoning=reasoning)


def hold(reasoning: str | None = None) -> Decision:
    return Decision(reasoning=reasoning)


def normalize_decision(value: DecisionLike) -> Decision:
    if value is None:
        return Decision()
    if isinstance(value, Decision):
        return value
    if isinstance(value, Order):
        return Decision(orders=[value])
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return Decision(orders=[Order.model_validate(order) for order in value])
    raise TypeError("agent decisions must be Decision, Order, a sequence of Order, or None")


def agent_name(agent: Any) -> str:
    name = getattr(agent, "__name__", None)
    return str(name) if name else agent.__class__.__name__


def resolve_agent_info(agent: Any, supplied: AgentInfo | None) -> AgentInfo:
    if supplied is not None:
        return supplied
    attached = getattr(agent, "agent_info", None)
    if attached is not None:
        return AgentInfo.model_validate(attached)
    return AgentInfo(name=agent_name(agent))


def invoke_agent(agent: SyncAgent | DecidingAgent, observation: Observation) -> Decision:
    target = cast(Callable[[Observation], Any], getattr(agent, "decide", agent))
    value = target(observation)
    if inspect.isawaitable(value):
        raise TypeError("async agents use bottrade.backtest_async()")
    return normalize_decision(cast(DecisionLike, value))


async def invoke_agent_async(
    agent: SyncAgent | AsyncAgent | DecidingAgent | AsyncDecidingAgent,
    observation: Observation,
) -> Decision:
    target = cast(Callable[[Observation], Any], getattr(agent, "decide", agent))
    value = target(observation)
    if inspect.isawaitable(value):
        value = await value
    return normalize_decision(cast(DecisionLike, value))
