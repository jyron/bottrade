"""Typed response models for the public BotTrade API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    """Forward-compatible base model for evolving API responses."""

    model_config = ConfigDict(extra="allow")


class Scenario(APIModel):
    id: str | None = None
    slug: str
    name: str
    description: str = ""
    status: str
    universe: list[str]
    starting_cash: float
    leverage_cap: float
    short_enabled: bool
    bar_resolution: str
    start_ts: datetime
    end_ts: datetime
    benchmark_symbol: str | None = None
    current_version: int | None = None


class AgentInfo(APIModel):
    """Reproducible identity attached to a benchmark run."""

    name: str
    framework: str = "python"
    model: str | None = None
    version: str | None = None
    source_url: str | None = None
    source_revision: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class Run(APIModel):
    id: str
    scenario_id: str | None = None
    scenario_version: int | None = None
    status: str
    bot_name: str | None = None
    cash: float
    starting_cash: float
    sim_time: datetime
    published: bool = False
    agent_info: AgentInfo | None = None


class Position(APIModel):
    symbol: str
    quantity: float
    avg_cost: float


class Bar(APIModel):
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class QueuedOrder(APIModel):
    id: str | None = None
    symbol: str
    side: str
    quantity: float
    reasoning: str | None = None


class Fill(APIModel):
    symbol: str
    side: str
    quantity: float
    fill_price: float
    slippage_bps: float | None = None
    total_value: float | None = None


class Results(APIModel):
    final_equity: float
    return_pct: float
    sharpe: float | None = None
    sortino: float | None = None
    max_drawdown: float | None = None
    volatility: float | None = None
    trade_count: int
    liquidated: bool


class EquityPoint(APIModel):
    sim_time: datetime
    equity: float


class RunSnapshot(APIModel):
    run: Run
    positions: list[Position] = Field(default_factory=list)
    queued_orders: list[QueuedOrder] = Field(default_factory=list)
    last_equity: dict[str, Any] | None = None


class MarketObservation(APIModel):
    sim_time: datetime
    bars: dict[str, list[Bar]]


class StepResult(APIModel):
    bars_advanced: int = 0
    new_sim_time: datetime | None = None
    fills: list[Fill] = Field(default_factory=list)
    equity: float
    cash: float
    positions_value: float | None = None
    done: bool
    liquidated: bool


class PublicRun(RunSnapshot):
    results: Results | None = None
    trades: list[dict[str, Any]] = Field(default_factory=list)
    equity_curve: list[EquityPoint] = Field(default_factory=list)


class Order(APIModel):
    """One order returned by a custom agent."""

    symbol: str
    side: Literal["buy", "sell", "short", "cover"]
    quantity: float = Field(gt=0)
    reasoning: str | None = None


class Decision(APIModel):
    """Orders and optional shared reasoning for one decision point."""

    orders: list[Order] = Field(default_factory=list)
    reasoning: str | None = None


class Observation(APIModel):
    """Complete input supplied to a custom agent at one decision point."""

    scenario: Scenario
    snapshot: RunSnapshot
    market: MarketObservation
    step_number: int

    @property
    def run_id(self) -> str:
        return self.snapshot.run.id

    @property
    def sim_time(self) -> datetime:
        return self.market.sim_time

    @property
    def cash(self) -> float:
        return self.snapshot.run.cash

    @property
    def positions(self) -> list[Position]:
        return self.snapshot.positions

    @property
    def bars(self) -> dict[str, list[Bar]]:
        return self.market.bars

    def position(self, symbol: str) -> Position | None:
        target = symbol.upper()
        return next((position for position in self.positions if position.symbol == target), None)
