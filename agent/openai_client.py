"""Responses API adapter. One instance owns one run's in-memory history."""

import json
from copy import deepcopy

from agent.model import ModelTurn, ToolCall, ToolResult
from agent.prompts import AGENT_INSTRUCTIONS
from agent.tool_schemas import tool_schemas


class OpenAIModelClient:
    def __init__(self, sdk_client: object, model_name: str) -> None:
        if not model_name.strip():
            raise ValueError("A model name is required")
        self.model_name = model_name
        self._sdk = sdk_client
        self._history: list[dict] = []
        self._question: str | None = None
        self._pending_ids: tuple[str, ...] = ()
        self.last_usage: dict[str, int] | None = None

    def respond(self, question: str, results: tuple[ToolResult, ...]) -> ModelTurn:
        if self._question is None:
            if results:
                raise ValueError("A new run cannot start with tool results")
            self._question = question
            self._history.append({"role": "user", "content": question})
        elif question != self._question or not self._pending_ids:
            raise ValueError("Create a new adapter for each question")
        if tuple(result.call_id for result in results) != self._pending_ids:
            raise ValueError("Tool results must match pending call IDs")
        for result in results:
            self._history.append({
                "type": "function_call_output",
                "call_id": result.call_id,
                "output": json.dumps(result.result, allow_nan=False),
            })
        response = self._sdk.responses.create(
            model=self.model_name,
            instructions=AGENT_INSTRUCTIONS,
            input=deepcopy(self._history),
            tools=tool_schemas(),
            max_output_tokens=2000,
            store=False,
            include=["reasoning.encrypted_content"],
        )
        if response.status != "completed":
            raise ValueError("Model response did not complete")
        calls = []
        for item in response.output:
            if item.type == "function_call":
                if not all(isinstance(value, str) for value in (item.name, item.arguments, item.call_id)):
                    raise ValueError("Invalid tool call fields")
                calls.append(ToolCall(item.name, item.arguments, item.call_id))
            elif item.type not in {"message", "reasoning"}:
                raise ValueError("Unsupported model output item")
            # Replay output in memory, including reasoning items required by
            # reasoning models. Never copy this raw history to the trace.
            self._history.append(item.model_dump(exclude_none=True))
        self._pending_ids = tuple(call.call_id for call in calls)
        usage = response.usage
        self.last_usage = None if usage is None else {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
        }
        return ModelTurn(calls=tuple(calls), answer=response.output_text)


def create_openai_client(api_key: str, model_name: str) -> OpenAIModelClient:
    """Construct lazily so offline analysis does not require SDK imports."""
    from openai import OpenAI

    sdk = OpenAI(api_key=api_key, timeout=30.0, max_retries=0,
                 base_url="https://api.openai.com/v1")
    return OpenAIModelClient(sdk, model_name)
