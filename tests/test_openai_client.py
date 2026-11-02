from copy import deepcopy
from types import SimpleNamespace

import pytest

from agent.model import ToolResult
from agent.openai_client import OpenAIModelClient, create_openai_client
from agent.tool_schemas import tool_schemas


class Item:
    def __init__(self, **fields):
        self.__dict__.update(fields)

    def model_dump(self, **kwargs):
        return dict(self.__dict__)


class FakeSDK:
    def __init__(self, responses):
        self.turns = iter(responses)
        self.requests = []
        self.responses = self

    def create(self, **kwargs):
        self.requests.append(deepcopy(kwargs))
        return next(self.turns)


def response(*items, text="", status="completed"):
    return SimpleNamespace(
        output=list(items), output_text=text, status=status,
        usage=SimpleNamespace(input_tokens=100, output_tokens=20, total_tokens=120),
    )


def test_adapter_replays_history_and_matches_call_ids():
    call = Item(type="function_call", name="analyze_concentration", arguments="{}", call_id="call-1", id="fc-1")
    sdk = FakeSDK([response(call), response(Item(type="message", role="assistant", content=[]), text="HHI is 0.34.")])
    adapter = OpenAIModelClient(sdk, "test-model")
    turn = adapter.respond("How concentrated?", ())
    assert turn.calls[0].call_id == "call-1"
    final = adapter.respond("How concentrated?", (ToolResult("call-1", {"hhi": 0.34}),))
    assert final.answer == "HHI is 0.34."
    request = sdk.requests[1]
    assert request["input"][1]["type"] == "function_call"
    assert request["input"][2] == {"type": "function_call_output", "call_id": "call-1", "output": '{"hhi": 0.34}'}
    assert request["store"] is False
    assert request["max_output_tokens"] == 2000
    assert len(request["tools"]) == 3
    assert "instructions" in request
    assert adapter.last_usage == {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}
    # The first request snapshot must not change when history is extended.
    assert len(sdk.requests[0]["input"]) == 1


def test_wrong_result_id_is_rejected_before_api_call():
    sdk = FakeSDK([response(Item(type="function_call", name="get_asset_data", arguments="{}", call_id="expected"))])
    adapter = OpenAIModelClient(sdk, "test-model")
    adapter.respond("Assets?", ())
    with pytest.raises(ValueError, match="call IDs"):
        adapter.respond("Assets?", (ToolResult("wrong", {}),))
    assert len(sdk.requests) == 1


@pytest.mark.parametrize("status", ["incomplete", "failed", "cancelled"])
def test_incomplete_responses_are_not_used(status):
    adapter = OpenAIModelClient(FakeSDK([response(text="Unfinished", status=status)]), "test-model")
    with pytest.raises(ValueError, match="did not complete"):
        adapter.respond("Analyze", ())


def test_strict_zero_argument_schemas():
    definitions = tool_schemas()
    assert {item["name"] for item in definitions} == {"get_asset_data", "calculate_allocation", "analyze_concentration"}
    for item in definitions:
        assert item["strict"] is True
        assert item["parameters"] == {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    definitions[0]["parameters"]["properties"]["injected"] = {}
    assert tool_schemas()[0]["parameters"]["properties"] == {}


def test_sdk_configuration_without_network(monkeypatch):
    captured = {}

    def factory(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("openai.OpenAI", factory)
    client = create_openai_client("test-only-key", "test-model")
    assert client.model_name == "test-model"
    assert captured["timeout"] == 30
    assert captured["max_retries"] == 0
    assert captured["base_url"] == "https://api.openai.com/v1"


def test_reasoning_items_replayed_in_memory():
    sdk = FakeSDK([response(
        Item(type="reasoning", id="r1", encrypted_content="opaque-content", summary=[]),
        Item(type="function_call", name="get_asset_data", arguments="{}", call_id="c1"),
    ), response(text="Done")])
    adapter = OpenAIModelClient(sdk, "test-model")
    adapter.respond("Assets?", ())
    adapter.respond("Assets?", (ToolResult("c1", {}),))
    assert sdk.requests[1]["input"][1]["type"] == "reasoning"


def test_installed_sdk_roundtrip_with_mock_http():
    """Exercise actual SDK serialization and response parsing, without network."""
    import json

    import httpx
    from openai import OpenAI

    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        output = ([{
            "type": "function_call", "id": "fc_1", "call_id": "call_1",
            "name": "analyze_concentration", "arguments": "{}", "status": "completed",
        }] if len(requests) == 1 else [{
            "type": "message", "id": "msg_1", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": "HHI is 0.34.", "annotations": []}],
        }])
        return httpx.Response(200, json={
            "id": "resp_1", "object": "response", "created_at": 1,
            "status": "completed", "model": "test-model", "output": output,
            "parallel_tool_calls": True, "tool_choice": "auto", "tools": body["tools"],
            "usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
        })

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        sdk = OpenAI(api_key="test-only-key", http_client=http, max_retries=0)
        adapter = OpenAIModelClient(sdk, "test-model")
        assert adapter.respond("How concentrated?", ()).calls[0].name == "analyze_concentration"
        assert adapter.respond("How concentrated?", (ToolResult("call_1", {"hhi": 0.34}),)).answer == "HHI is 0.34."
    assert requests[1]["input"][-1]["call_id"] == "call_1"
