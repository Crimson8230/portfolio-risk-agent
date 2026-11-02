"""Provider-independent model boundary used by the orchestration loop."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: str
    call_id: str


@dataclass(frozen=True)
class ToolResult:
    call_id: str
    result: dict


@dataclass(frozen=True)
class ModelTurn:
    calls: tuple[ToolCall, ...] = ()
    answer: str = ""


class ModelClient(Protocol):
    """One client instance per run; implementations manage provider history.

    Only question and executed tool results cross this boundary. The raw
    portfolio and credentials never belong in these messages or trace events.
    Production adapters must enforce transport timeouts and token budgets.
    """

    model_name: str

    def respond(self, question: str, results: tuple[ToolResult, ...]) -> ModelTurn: ...
