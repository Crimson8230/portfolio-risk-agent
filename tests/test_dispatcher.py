import json
from pathlib import Path

import pytest

from agent.dispatcher import Dispatcher, ToolExecutionError
from agent.trace import ExecutionTrace
from portfolio.loaders import load_catalog, load_portfolio


@pytest.fixture
def context():
    trace = ExecutionTrace("simulated")
    sample = Path(__file__).resolve().parent.parent / "data" / "sample_portfolio.json"
    return Dispatcher(load_portfolio(sample), load_catalog(), trace), trace


@pytest.mark.parametrize("name", ["get_asset_data", "calculate_allocation", "analyze_concentration"])
def test_allowed_tools(context, name):
    dispatcher, trace = context
    result = dispatcher.dispatch(name, "{}", "call-1")
    assert trace.events[-1]["result"] == result
    assert [event["event_type"] for event in trace.events] == ["tool_requested", "tool_completed"]
    assert trace.events[-1]["call_id"] == "call-1"


def test_trade_blocked_and_run_stopped(context):
    dispatcher, trace = context
    with pytest.raises(ToolExecutionError, match="UNAUTHORIZED_TOOL"):
        dispatcher.dispatch("execute_trade", "{}", "call-1")
    with pytest.raises(ToolExecutionError, match="RUN_ALREADY_STOPPED"):
        dispatcher.dispatch("get_asset_data", "{}", "call-2")
    assert dispatcher.attempts == 2
    assert not any(event["event_type"] == "tool_completed" for event in trace.events)


@pytest.mark.parametrize("arguments", ["", "{", "null", "[]", "true", '{"portfolio":"secret-payload"}', '"secret-payload"', " " * 1025])
def test_bad_arguments_are_rejected_without_logging_payload(context, arguments):
    dispatcher, trace = context
    with pytest.raises(ToolExecutionError, match="INVALID_ARGUMENTS"):
        dispatcher.dispatch("calculate_allocation", arguments, "call-1")
    assert "secret-payload" not in trace.render()


def test_tool_limit(context):
    dispatcher, trace = context
    for index in range(8):
        dispatcher.dispatch("analyze_concentration", "{}", str(index))
    with pytest.raises(ToolExecutionError, match="TOOL_LIMIT_EXCEEDED"):
        dispatcher.dispatch("analyze_concentration", "{}", "9")
    assert len([event for event in trace.events if event["event_type"] == "tool_completed"]) == 8


def test_duplicate_call_id(context):
    dispatcher, _ = context
    dispatcher.dispatch("get_asset_data", "{}", "same")
    with pytest.raises(ToolExecutionError, match="INVALID_CALL_ID"):
        dispatcher.dispatch("get_asset_data", "{}", "same")


def test_tool_error_does_not_leak_exception(context, monkeypatch):
    dispatcher, trace = context

    def broken(*args):
        raise RuntimeError("secret-credential")

    monkeypatch.setattr("agent.dispatcher.analyze_concentration", broken)
    with pytest.raises(ToolExecutionError, match="TOOL_FAILED"):
        dispatcher.dispatch("analyze_concentration", "{}", "call-1")
    assert trace.events[-1]["event_type"] == "tool_failed"
    assert "secret-credential" not in trace.render()


def test_trace_export_and_overwrite_protection(context, tmp_path):
    dispatcher, trace = context
    dispatcher.dispatch("analyze_concentration", "{}", "call-1")
    trace.finish("success")
    path = tmp_path / "trace.json"
    trace.export(path)
    result = json.loads(path.read_text())
    assert result["status"] == "success"
    assert result["events"][-1]["result"]["hhi"] == 0.34
    assert [event["sequence"] for event in result["events"]] == [1, 2]
    with pytest.raises(FileExistsError):
        trace.export(path)


def test_terminal_controls_are_escaped():
    trace = ExecutionTrace("simulated")
    trace.record("tool_requested", tool_name="\x1b[31m")
    assert "\x1b" not in trace.render()
    assert "\\u001b" in trace.render()
