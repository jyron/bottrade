"""Manual backtest session for explicit lifecycle control."""

from __future__ import annotations

from .agents import DecisionLike, normalize_decision
from .client import BotTradeClient
from .errors import IncompleteRunError
from .models import AgentInfo, Observation, Results, Run, Scenario, StepResult

TERMINAL_STATUSES = frozenset({"completed", "done", "liquidated"})


class BacktestSession:
    """A manually controlled BotTrade run."""

    def __init__(
        self,
        scenario: str,
        *,
        agent_info: AgentInfo,
        lookback: int = 50,
        resume_run_id: str | None = None,
        api_key: str | None = None,
        client: BotTradeClient | None = None,
    ) -> None:
        self.scenario_slug = scenario
        self.agent_info = agent_info
        self.lookback = lookback
        self.resume_run_id = resume_run_id
        self._owned_client = client is None
        self.client = client or (
            BotTradeClient(api_key) if api_key else BotTradeClient.from_env()
        )
        self.scenario: Scenario | None = None
        self.run: Run | None = None
        self.step_number = 0

    def __enter__(self) -> BacktestSession:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        if self._owned_client:
            self.client.close()

    @property
    def run_id(self) -> str:
        if self.run is None:
            raise RuntimeError("call start() or enter the session first")
        return self.run.id

    @property
    def active(self) -> bool:
        snapshot = self.client.get_run(self.run_id)
        self.run = snapshot.run
        return self.run.status.lower() not in TERMINAL_STATUSES

    def start(self) -> Run:
        if self.run is not None:
            return self.run
        self.scenario = self.client.get_scenario(self.scenario_slug)
        if self.resume_run_id:
            self.run = self.client.get_run(self.resume_run_id).run
        else:
            self.run = self.client.start_run(
                self.scenario.slug,
                bot_name=self.agent_info.name,
                agent_info=self.agent_info,
            )
        return self.run

    def observe(self) -> Observation:
        if self.scenario is None:
            self.start()
        assert self.scenario is not None
        snapshot = self.client.get_run(self.run_id)
        self.run = snapshot.run
        market = self.client.get_market(
            self.run_id,
            symbols=self.scenario.universe,
            lookback=self.lookback,
        )
        return Observation(
            scenario=self.scenario,
            snapshot=snapshot,
            market=market,
            step_number=self.step_number,
        )

    def submit(self, decision: DecisionLike) -> None:
        normalized = normalize_decision(decision)
        for order in normalized.orders:
            self.client.queue_trade(
                self.run_id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                reasoning=order.reasoning or normalized.reasoning,
            )

    def step(self) -> StepResult:
        result = self.client.step(self.run_id)
        self.step_number += result.bars_advanced
        return result

    def results(self) -> Results:
        if self.active:
            raise IncompleteRunError(f"Run {self.run_id} is active")
        return self.client.get_results(self.run_id)

    def publish(self) -> Results:
        return self.client.publish_run(self.run_id, confirm=True)


def session(
    scenario: str,
    *,
    agent_info: AgentInfo,
    lookback: int = 50,
    resume_run_id: str | None = None,
    api_key: str | None = None,
    client: BotTradeClient | None = None,
) -> BacktestSession:
    """Create a manually controlled backtest session."""

    return BacktestSession(
        scenario,
        agent_info=agent_info,
        lookback=lookback,
        resume_run_id=resume_run_id,
        api_key=api_key,
        client=client,
    )
