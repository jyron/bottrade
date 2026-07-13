"""Synchronous and asynchronous clients for the BotTrade REST API."""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, TypeVar
from urllib.parse import quote

import httpx
from pydantic import BaseModel

from .errors import (
    APIError,
    AuthenticationRequired,
    PublicationConfirmationRequired,
)
from .models import (
    AgentInfo,
    MarketObservation,
    PublicRun,
    QueuedOrder,
    Results,
    Run,
    RunSnapshot,
    Scenario,
    StepResult,
)

DEFAULT_API_URL = "https://bot-trade.org"
DEFAULT_MCP_URL = "https://mcp.bot-trade.org/mcp"
RETRYABLE_STATUS_CODES = frozenset({502, 503, 504})

ModelT = TypeVar("ModelT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Retry transient edge failures only when replaying the request is safe."""

    attempts: int = 4
    base_delay_seconds: float = 0.5

    def delay(self, retry_number: int) -> float:
        return float(self.base_delay_seconds * (2**retry_number))


def _message(payload: Any, fallback: str) -> str:
    if isinstance(payload, Mapping):
        for key in ("detail", "message", "error", "title"):
            value = payload.get(key)
            if value:
                return str(value)
    return fallback


def _decode_response(response: httpx.Response) -> Any:
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if response.is_error:
        raise APIError(
            response.status_code,
            _message(payload, response.text or response.reason_phrase),
            method=response.request.method,
            url=str(response.request.url),
            payload=payload,
        )
    return payload


class _ClientConfig:
    def __init__(self, api_key: str | None, base_url: str) -> None:
        self.api_key = (api_key or "").strip() or None
        self.base_url = base_url.rstrip("/")

    def headers(self, protected: bool) -> dict[str, str]:
        headers = {"Accept": "application/json", "User-Agent": "bottrade-python/0.2.0"}
        if protected:
            if self.api_key is None:
                raise AuthenticationRequired(
                    "This operation requires BOTTRADE_API_KEY or an explicit api_key."
                )
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


class BotTradeClient:
    """Typed synchronous BotTrade client.

    The client retries GET requests and idempotent writes on transient edge failures.
    Starting a run is intentionally not retried because the API does not accept an
    idempotency key for run creation.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_API_URL,
        timeout: float = 45.0,
        retry_policy: RetryPolicy | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._config = _ClientConfig(api_key, base_url)
        self._retry_policy = retry_policy or RetryPolicy()
        self._http = httpx.Client(timeout=timeout, transport=transport)

    @classmethod
    def from_env(cls, **kwargs: Any) -> BotTradeClient:
        return cls(
            os.getenv("BOTTRADE_API_KEY") or os.getenv("BOT_API_KEY"),
            base_url=os.getenv("BOTTRADE_API", DEFAULT_API_URL),
            **kwargs,
        )

    def __enter__(self) -> BotTradeClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        protected: bool,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
        safe_to_retry: bool = False,
    ) -> Any:
        attempts = self._retry_policy.attempts if safe_to_retry or method == "GET" else 1
        last_error: httpx.RequestError | None = None
        for attempt in range(attempts):
            try:
                response = self._http.request(
                    method,
                    self._config.base_url + path,
                    headers=self._config.headers(protected),
                    params=params,
                    json=json,
                )
            except httpx.RequestError as error:
                last_error = error
                if attempt + 1 == attempts:
                    raise
            else:
                if response.status_code not in RETRYABLE_STATUS_CODES or attempt + 1 == attempts:
                    return _decode_response(response)
            time.sleep(self._retry_policy.delay(attempt))
        assert last_error is not None
        raise last_error

    def list_scenarios(self) -> list[Scenario]:
        payload = self._request("GET", "/api/v1/scenarios", protected=False)
        return [Scenario.model_validate(item) for item in payload["scenarios"]]

    def get_scenario(self, slug_or_id: str) -> Scenario:
        payload = self._request(
            "GET", f"/api/v1/scenarios/{quote(slug_or_id, safe='')}", protected=False
        )
        return Scenario.model_validate(payload["scenario"])

    def start_run(
        self,
        scenario_slug: str,
        *,
        bot_name: str | None = None,
        agent_info: AgentInfo | None = None,
    ) -> Run:
        """Create a private active run; this does not advance or finish it."""

        body: dict[str, Any] = {"scenario_slug": scenario_slug}
        if bot_name:
            body["bot_name"] = bot_name
        if agent_info:
            body["agent_info"] = agent_info.model_dump(mode="json", exclude_none=True)
        payload = self._request("POST", "/api/v1/runs", protected=True, json=body)
        return Run.model_validate(payload["run"])

    def get_run(self, run_id: str) -> RunSnapshot:
        payload = self._request(
            "GET", f"/api/v1/runs/{quote(run_id, safe='')}", protected=True
        )
        return RunSnapshot.model_validate(payload)

    def get_market(
        self, run_id: str, *, symbols: list[str] | None = None, lookback: int = 50
    ) -> MarketObservation:
        params: dict[str, Any] = {"lookback": lookback}
        if symbols:
            params["symbols"] = ",".join(symbols)
        payload = self._request(
            "GET",
            f"/api/v1/runs/{quote(run_id, safe='')}/market",
            protected=True,
            params=params,
        )
        return MarketObservation.model_validate(payload)

    def queue_trade(
        self,
        run_id: str,
        *,
        symbol: str,
        side: str,
        quantity: float,
        reasoning: str | None = None,
        idempotency_key: str | None = None,
    ) -> QueuedOrder:
        body: dict[str, Any] = {
            "symbol": symbol.upper(),
            "side": side.lower(),
            "quantity": quantity,
            "idempotency_key": idempotency_key or str(uuid.uuid4()),
        }
        if reasoning:
            body["reasoning"] = reasoning[:500]
        payload = self._request(
            "POST",
            f"/api/v1/runs/{quote(run_id, safe='')}/trades",
            protected=True,
            json=body,
            safe_to_retry=True,
        )
        return QueuedOrder.model_validate(payload["order"])

    def step(
        self, run_id: str, *, count: int = 1, idempotency_key: str | None = None
    ) -> StepResult:
        payload = self._request(
            "POST",
            f"/api/v1/runs/{quote(run_id, safe='')}/step",
            protected=True,
            json={"count": count, "idempotency_key": idempotency_key or str(uuid.uuid4())},
            safe_to_retry=True,
        )
        return StepResult.model_validate(payload)

    def get_results(self, run_id: str) -> Results:
        payload = self._request(
            "GET", f"/api/v1/runs/{quote(run_id, safe='')}/results", protected=True
        )
        return Results.model_validate(payload["results"])

    def publish_run(self, run_id: str, *, confirm: bool = False) -> Results:
        if not confirm:
            raise PublicationConfirmationRequired(
                "Publishing makes the run and its trades public. Pass confirm=True to continue."
            )
        payload = self._request(
            "POST",
            f"/api/v1/runs/{quote(run_id, safe='')}/publish",
            protected=True,
            safe_to_retry=True,
        )
        return Results.model_validate(payload["results"])

    def get_public_run(self, run_id: str) -> PublicRun:
        payload = self._request(
            "GET", f"/api/v1/runs/{quote(run_id, safe='')}/public", protected=False
        )
        return PublicRun.model_validate(payload)

    def run_url(self, run_id: str) -> str:
        return f"{self._config.base_url}/run/{quote(run_id, safe='')}"

    def badge_url(self, run_id: str) -> str:
        return f"{self.run_url(run_id)}/badge.svg"

    def badge_markdown(self, run_id: str) -> str:
        return f"[![Tested on BotTrade]({self.badge_url(run_id)})]({self.run_url(run_id)})"


class AsyncBotTradeClient:
    """Typed asynchronous BotTrade client with the same safety guarantees."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_API_URL,
        timeout: float = 45.0,
        retry_policy: RetryPolicy | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = _ClientConfig(api_key, base_url)
        self._retry_policy = retry_policy or RetryPolicy()
        self._http = httpx.AsyncClient(timeout=timeout, transport=transport)

    @classmethod
    def from_env(cls, **kwargs: Any) -> AsyncBotTradeClient:
        return cls(
            os.getenv("BOTTRADE_API_KEY") or os.getenv("BOT_API_KEY"),
            base_url=os.getenv("BOTTRADE_API", DEFAULT_API_URL),
            **kwargs,
        )

    async def __aenter__(self) -> AsyncBotTradeClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        protected: bool,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
        safe_to_retry: bool = False,
    ) -> Any:
        attempts = self._retry_policy.attempts if safe_to_retry or method == "GET" else 1
        last_error: httpx.RequestError | None = None
        for attempt in range(attempts):
            try:
                response = await self._http.request(
                    method,
                    self._config.base_url + path,
                    headers=self._config.headers(protected),
                    params=params,
                    json=json,
                )
            except httpx.RequestError as error:
                last_error = error
                if attempt + 1 == attempts:
                    raise
            else:
                if response.status_code not in RETRYABLE_STATUS_CODES or attempt + 1 == attempts:
                    return _decode_response(response)
            await asyncio.sleep(self._retry_policy.delay(attempt))
        assert last_error is not None
        raise last_error

    async def list_scenarios(self) -> list[Scenario]:
        payload = await self._request("GET", "/api/v1/scenarios", protected=False)
        return [Scenario.model_validate(item) for item in payload["scenarios"]]

    async def get_scenario(self, slug_or_id: str) -> Scenario:
        payload = await self._request(
            "GET", f"/api/v1/scenarios/{quote(slug_or_id, safe='')}", protected=False
        )
        return Scenario.model_validate(payload["scenario"])

    async def start_run(
        self,
        scenario_slug: str,
        *,
        bot_name: str | None = None,
        agent_info: AgentInfo | None = None,
    ) -> Run:
        """Create a private active run; this does not advance or finish it."""

        body: dict[str, Any] = {"scenario_slug": scenario_slug}
        if bot_name:
            body["bot_name"] = bot_name
        if agent_info:
            body["agent_info"] = agent_info.model_dump(mode="json", exclude_none=True)
        payload = await self._request("POST", "/api/v1/runs", protected=True, json=body)
        return Run.model_validate(payload["run"])

    async def get_run(self, run_id: str) -> RunSnapshot:
        payload = await self._request(
            "GET", f"/api/v1/runs/{quote(run_id, safe='')}", protected=True
        )
        return RunSnapshot.model_validate(payload)

    async def get_market(
        self, run_id: str, *, symbols: list[str] | None = None, lookback: int = 50
    ) -> MarketObservation:
        params: dict[str, Any] = {"lookback": lookback}
        if symbols:
            params["symbols"] = ",".join(symbols)
        payload = await self._request(
            "GET",
            f"/api/v1/runs/{quote(run_id, safe='')}/market",
            protected=True,
            params=params,
        )
        return MarketObservation.model_validate(payload)

    async def queue_trade(
        self,
        run_id: str,
        *,
        symbol: str,
        side: str,
        quantity: float,
        reasoning: str | None = None,
        idempotency_key: str | None = None,
    ) -> QueuedOrder:
        body: dict[str, Any] = {
            "symbol": symbol.upper(),
            "side": side.lower(),
            "quantity": quantity,
            "idempotency_key": idempotency_key or str(uuid.uuid4()),
        }
        if reasoning:
            body["reasoning"] = reasoning[:500]
        payload = await self._request(
            "POST",
            f"/api/v1/runs/{quote(run_id, safe='')}/trades",
            protected=True,
            json=body,
            safe_to_retry=True,
        )
        return QueuedOrder.model_validate(payload["order"])

    async def step(
        self, run_id: str, *, count: int = 1, idempotency_key: str | None = None
    ) -> StepResult:
        payload = await self._request(
            "POST",
            f"/api/v1/runs/{quote(run_id, safe='')}/step",
            protected=True,
            json={"count": count, "idempotency_key": idempotency_key or str(uuid.uuid4())},
            safe_to_retry=True,
        )
        return StepResult.model_validate(payload)

    async def get_results(self, run_id: str) -> Results:
        payload = await self._request(
            "GET", f"/api/v1/runs/{quote(run_id, safe='')}/results", protected=True
        )
        return Results.model_validate(payload["results"])

    async def publish_run(self, run_id: str, *, confirm: bool = False) -> Results:
        if not confirm:
            raise PublicationConfirmationRequired(
                "Publishing makes the run and its trades public. Pass confirm=True to continue."
            )
        payload = await self._request(
            "POST",
            f"/api/v1/runs/{quote(run_id, safe='')}/publish",
            protected=True,
            safe_to_retry=True,
        )
        return Results.model_validate(payload["results"])

    async def get_public_run(self, run_id: str) -> PublicRun:
        payload = await self._request(
            "GET", f"/api/v1/runs/{quote(run_id, safe='')}/public", protected=False
        )
        return PublicRun.model_validate(payload)

    def run_url(self, run_id: str) -> str:
        return f"{self._config.base_url}/run/{quote(run_id, safe='')}"

    def badge_url(self, run_id: str) -> str:
        return f"{self.run_url(run_id)}/badge.svg"

    def badge_markdown(self, run_id: str) -> str:
        return f"[![Tested on BotTrade]({self.badge_url(run_id)})]({self.run_url(run_id)})"
