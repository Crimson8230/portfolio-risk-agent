"""Bounded model → tool → model orchestration, independent of an API SDK."""

from dataclasses import dataclass
from time import perf_counter

from agent.dispatcher import Dispatcher, ToolExecutionError
from agent.model import ModelClient, ModelTurn, ToolResult
from agent.trace import ExecutionTrace
from portfolio.models import Asset, Portfolio

MAX_TOOL_ROUNDS = 4
MAX_MODEL_REQUESTS = 5


@dataclass(frozen=True)
class RunResult:
    status: str
    answer: str
    verified_facts: tuple[dict, ...]
    error_code: str | None
    trace: ExecutionTrace


def run_agent(
    question: str,
    portfolio: Portfolio,
    catalog: dict[str, Asset],
    client: ModelClient,
    *,
    mode: str = "agent",
) -> RunResult:
    """Run with already validated application context and no conversation memory."""
    trace = ExecutionTrace(mode)
    facts: list[dict] = []

    def finish(status: str, answer: str = "", error_code: str | None = None) -> RunResult:
        trace.record("run_finished", status=status, answer=answer,
                     verified_facts=list(facts), error_code=error_code)
        trace.finish(status)
        return RunResult(status, answer, tuple(facts), error_code, trace)

    if not question.strip() or len(question) > 2000:
        trace.record("input_rejected", error_code="INVALID_QUESTION")
        return finish("rejected", error_code="INVALID_QUESTION")
    trace.record("input_validated", question=question, model=client.model_name)
    dispatcher = Dispatcher(portfolio, catalog, trace)
    results: tuple[ToolResult, ...] = ()
    rounds = 0
    for request_number in range(1, MAX_MODEL_REQUESTS + 1):
        trace.record("model_requested", request_number=request_number)
        started = perf_counter()
        try:
            turn = client.respond(question, results)
            if not isinstance(turn, ModelTurn):
                raise ValueError("Invalid normalized model response")
        except Exception:
            trace.record("model_failed", request_number=request_number,
                         duration_ms=(perf_counter() - started) * 1000,
                         error_code="MODEL_FAILED")
            return finish("error", error_code="MODEL_FAILED")
        trace.record("model_responded", request_number=request_number,
                     duration_ms=(perf_counter() - started) * 1000,
                     tool_call_count=len(turn.calls),
                     usage=getattr(client, "last_usage", None))
        if not turn.calls:
            if not turn.answer.strip() or len(turn.answer) > 16000:
                trace.record("output_rejected", error_code="INVALID_MODEL_ANSWER")
                return finish("rejected", error_code="INVALID_MODEL_ANSWER")
            return finish("success", answer=turn.answer)
        if rounds >= MAX_TOOL_ROUNDS:
            trace.record("guardrail_blocked", error_code="TOOL_ROUND_LIMIT_EXCEEDED",
                         requested_tool_count=len(turn.calls))
            return finish("rejected", error_code="TOOL_ROUND_LIMIT_EXCEEDED")
        rounds += 1
        pending_results = []
        for call in turn.calls:
            try:
                output = dispatcher.dispatch(call.name, call.arguments, call.call_id)
            except ToolExecutionError as error:
                code = str(error)
                return finish("error" if code == "TOOL_FAILED" else "rejected", error_code=code)
            facts.append({"tool_name": call.name, "call_id": call.call_id, "result": output})
            pending_results.append(ToolResult(call.call_id, output))
        results = tuple(pending_results)
    trace.record("guardrail_blocked", error_code="MODEL_REQUEST_LIMIT_EXCEEDED")
    return finish("rejected", error_code="MODEL_REQUEST_LIMIT_EXCEEDED")
