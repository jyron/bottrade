"""Public exceptions raised by the BotTrade SDK."""

from __future__ import annotations

from typing import Any


class BotTradeError(Exception):
    """Base exception for SDK failures."""


class AuthenticationRequired(BotTradeError):
    """Raised before a protected request when no API key was configured."""


class PublicationConfirmationRequired(BotTradeError):
    """Raised when publication was requested without explicit confirmation."""


class APIError(BotTradeError):
    """A non-success response returned by BotTrade."""

    def __init__(
        self,
        status_code: int,
        message: str,
        *,
        method: str,
        url: str,
        payload: Any = None,
    ) -> None:
        super().__init__(f"BotTrade API {status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.method = method
        self.url = url
        self.payload = payload
