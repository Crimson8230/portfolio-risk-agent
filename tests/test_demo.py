import json
from pathlib import Path

from agent.demo import main

SAMPLE = str(Path(__file__).resolve().parent.parent / "data" / "sample_portfolio.json")


def test_scripted_demo_exports_trace_without_api_key(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    target = tmp_path / "trace.json"
    assert main([SAMPLE, "--trace-out", str(target)]) == 0
    trace = json.loads(target.read_text())
    assert trace["mode"] == "simulated"
    assert trace["status"] == "success"
    assert trace["events"][-1]["verified_facts"][0]["result"]["hhi"] == 0.34
    assert "no LLM was used" in capsys.readouterr().out


def test_blocked_demo_exports_rejection(tmp_path, capsys):
    target = tmp_path / "trace.json"
    assert main([SAMPLE, "--blocked", "--trace-out", str(target)]) == 1
    trace = json.loads(target.read_text())
    assert trace["status"] == "rejected"
    assert any(event.get("error_code") == "UNAUTHORIZED_TOOL" for event in trace["events"])
    assert not any(event["event_type"] == "tool_completed" for event in trace["events"])


def test_demo_does_not_overwrite_trace(tmp_path, capsys):
    target = tmp_path / "existing.json"
    target.write_text("keep me")
    assert main([SAMPLE, "--trace-out", str(target)]) == 1
    assert target.read_text() == "keep me"
