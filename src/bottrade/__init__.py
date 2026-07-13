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
    IncompleteRunError,
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
from .workflows import BenchmarkOutcome, format_results, require_completed_results, run_buy_and_hold

__all__ = [
    "DEFAULT_API_URL",
    "DEFAULT_MCP_URL",
    "APIError",
    "AsyncBotTradeClient",
    "AuthenticationRequired",
    "Bar",
    "BenchmarkOutcome",
    "BotTradeClient",
    "BotTradeError",
    "Fill",
    "IncompleteRunError",
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
    "format_results",
    "require_completed_results",
    "run_buy_and_hold",
]

__version__ = "0.1.1"
