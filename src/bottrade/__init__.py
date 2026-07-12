"""BotTrade Python SDK."""

from .client import (
    DEFAULT_API_URL,
    DEFAULT_MCP_URL,
    AsyncBotTradeClient,
    BotTradeClient,
    RetryPolicy,
)
from .errors import (
    APIError,
    AuthenticationRequired,
    BotTradeError,
    PublicationConfirmationRequired,
)
from .models import (
    Bar,
    Fill,
    MarketObservation,
    Position,
    PublicRun,
    QueuedOrder,
    Results,
    Run,
    RunSnapshot,
    Scenario,
    StepResult,
)

__all__ = [
    "DEFAULT_API_URL",
    "DEFAULT_MCP_URL",
    "APIError",
    "AsyncBotTradeClient",
    "AuthenticationRequired",
    "Bar",
    "BotTradeClient",
    "BotTradeError",
    "Fill",
    "MarketObservation",
    "Position",
    "PublicRun",
    "PublicationConfirmationRequired",
    "QueuedOrder",
    "Results",
    "RetryPolicy",
    "Run",
    "RunSnapshot",
    "Scenario",
    "StepResult",
]

__version__ = "0.1.0"
