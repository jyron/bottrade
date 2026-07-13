"""Explicit reference strategies built on the same custom-agent interface."""

from __future__ import annotations

from dataclasses import dataclass

from .agents import buy, hold
from .models import AgentInfo, Decision, Observation, Order


@dataclass(frozen=True, slots=True)
class BuyAndHold:
    quantity: float = 10
    symbol: str | None = None

    @property
    def agent_info(self) -> AgentInfo:
        return AgentInfo(
            name="Buy and hold",
            framework="bottrade",
            version="1",
            config={"quantity": self.quantity, "symbol": self.symbol},
        )

    def decide(self, observation: Observation) -> Order | Decision:
        symbol = self.symbol or observation.scenario.benchmark_symbol
        symbol = symbol or observation.scenario.universe[0]
        if observation.position(symbol) is None:
            return buy(symbol, self.quantity, "Open the reference buy-and-hold position.")
        return hold("Position is open.")


def buy_and_hold(quantity: float = 10, symbol: str | None = None) -> BuyAndHold:
    """Create the explicit buy-and-hold reference agent."""

    return BuyAndHold(quantity=quantity, symbol=symbol)
