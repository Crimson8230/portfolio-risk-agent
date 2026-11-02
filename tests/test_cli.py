import json
from pathlib import Path

from cli import main


def test_offline_cli_without_credentials(capsys, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    sample = Path(__file__).resolve().parent.parent / "data" / "sample_portfolio.json"
    assert main([str(sample)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "offline"
    assert output["concentration"]["hhi"] == 0.34
    assert output["allocation"]["total_value_eur"] == "10000"


def test_cli_rejection_is_safe_json(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text("invalid")
    assert main([str(path)]) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "rejected"
    assert "Traceback" not in output["error"]


def test_question_without_key_is_cleanly_disabled(capsys, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)
    sample = Path(__file__).resolve().parent.parent / "data" / "sample_portfolio.json"
    assert main([str(sample), "--question", "How concentrated?"]) == 1
    assert "requires OPENAI_API_KEY" in capsys.readouterr().out


def test_live_cli_with_fake_adapter_exports_trace(tmp_path, capsys, monkeypatch):
    from agent.demo import ScriptedDemoClient

    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.setattr("agent.openai_client.create_openai_client", lambda *args: ScriptedDemoClient())
    sample = Path(__file__).resolve().parent.parent / "data" / "sample_portfolio.json"
    target = tmp_path / "trace.json"
    assert main([str(sample), "--question", "How concentrated?", "--trace-out", str(target)]) == 0
    exported = json.loads(target.read_text())
    assert exported["status"] == "success"
    assert "test-only-key" not in target.read_text()
    assert "Verified tool facts" in capsys.readouterr().out


def test_invalid_portfolio_is_rejected_before_model_initialization(capsys, monkeypatch):
    def forbidden(*args):
        raise AssertionError("Model client must not be initialized for invalid input")

    monkeypatch.setattr("agent.openai_client.create_openai_client", forbidden)
    path = Path(__file__).resolve().parent.parent / "data" / "invalid_portfolio.json"
    assert main([str(path), "--question", "Analyze this portfolio"]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "rejected"
