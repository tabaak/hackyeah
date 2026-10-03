"""LLM routing (app/llm.py): which provider sees which data, failure behaviour, and the exact HTTP request
produced by the real OpenAI SDK (through a mock transport, no network)."""
import json
from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError

from app import llm
from app.llm import LLMUnavailable, chat, pick_provider
from app.schemas.common import Classification

MESSAGES = [{"role": "user", "content": "Is the claim supported?"}]
COMPLETION = {
    "id": "chatcmpl-1", "object": "chat.completion", "created": 1, "model": "m",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "4"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
}
TOOLS = [{"type": "function", "function": {"name": "search_documents", "parameters": {"type": "object", "properties": {}}}}]


# --- routing ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("labels,provider", [
    ([], "cloud"),
    (["public"], "cloud"),
    (["public", "public"], "cloud"),
    (["internal"], "local"),
    (["confidential"], "local"),
    (["restricted"], "local"),
    (["public", "internal"], "local"),
    (["public", "confidential", "public"], "local"),
])
def test_routing_by_labels(labels, provider):
    assert pick_provider(labels) == provider


def test_enum_and_string_labels_are_equivalent():
    assert pick_provider([Classification.confidential]) == pick_provider(["confidential"]) == "local"
    assert pick_provider([Classification.public]) == "cloud"


def test_labels_may_be_a_generator():
    assert pick_provider(c for c in ["public", "internal"]) == "local"


def test_unknown_label_fails_closed():
    with pytest.raises(ValueError):
        pick_provider(["top-secret"])


def test_labels_are_required():
    with pytest.raises(TypeError):
        pick_provider()
    with pytest.raises(TypeError):
        chat(MESSAGES)


@pytest.mark.parametrize("field", ["openai_api_key", "openai_model"])
def test_cloud_disabled_without_key_or_model(test_settings, monkeypatch, field):
    monkeypatch.setattr(test_settings, field, "")
    assert pick_provider(["public"]) == "local"


def test_force_local(test_settings, monkeypatch):
    monkeypatch.setattr(test_settings, "llm_force", "local")
    assert pick_provider(["public"]) == "local"


def test_force_cannot_send_closed_data_to_cloud(test_settings, monkeypatch):
    monkeypatch.setattr(test_settings, "llm_force", "cloud")
    assert pick_provider(["confidential"]) == "local"


# --- chat() with fake clients -----------------------------------------------------------------------

class FakeClient:
    def __init__(self, result=None, error=None):
        self.calls = []

        def create(**kwargs):
            self.calls.append(kwargs)
            if error:
                raise error
            return result

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


@pytest.fixture
def clients(monkeypatch):
    fakes = {"cloud": FakeClient(result="cloud-answer"), "local": FakeClient(result="local-answer")}
    monkeypatch.setattr(llm, "_client", lambda provider: fakes[provider])
    return fakes


def test_public_goes_to_cloud_model(clients):
    assert chat(MESSAGES, ["public"], tools=TOOLS, temperature=0.2) == ("cloud-answer", "cloud")
    assert clients["cloud"].calls == [{"model": "gpt-test", "messages": MESSAGES, "tools": TOOLS, "temperature": 0.2}]
    assert clients["local"].calls == []


def test_confidential_goes_to_local_model(clients):
    assert chat(MESSAGES, ["public", "confidential"], max_tokens=50) == ("local-answer", "local")
    assert clients["local"].calls == [{"model": "bonsai-2-27b", "messages": MESSAGES, "max_tokens": 50}]
    assert clients["cloud"].calls == []


def _request():
    return httpx.Request("POST", "http://localhost:8000/v1/chat/completions")


@pytest.mark.parametrize("error", [APIConnectionError(request=_request()), APITimeoutError(request=_request())],
                         ids=["connection", "timeout"])
def test_local_outage_never_falls_back_to_cloud(monkeypatch, error):
    fakes = {"cloud": FakeClient(result="cloud-answer"), "local": FakeClient(error=error)}
    monkeypatch.setattr(llm, "_client", lambda provider: fakes[provider])
    with pytest.raises(LLMUnavailable, match="local LLM unreachable"):
        chat(MESSAGES, ["confidential"])
    assert len(fakes["local"].calls) == 1 and fakes["cloud"].calls == []


def test_other_errors_propagate_unchanged(monkeypatch):
    fakes = {"local": FakeClient(error=ValueError("bad request")), "cloud": FakeClient()}
    monkeypatch.setattr(llm, "_client", lambda provider: fakes[provider])
    with pytest.raises(ValueError, match="bad request"):
        chat(MESSAGES, ["internal"])


def test_cloud_client_needs_a_key(test_settings, monkeypatch):
    monkeypatch.setattr(test_settings, "openai_api_key", "")
    with pytest.raises(LLMUnavailable, match="OPENAI_API_KEY"):
        llm._client("cloud")


def test_clients_are_reused():
    assert llm._client("local") is llm._client("local")
    assert llm._client("cloud") is not llm._client("local")


# --- real OpenAI SDK, mock transport ----------------------------------------------------------------

@pytest.fixture
def wire(monkeypatch):
    """Real OpenAI clients whose HTTP goes to a recorder. Set `wire.fail_hosts` to simulate outages."""
    state = SimpleNamespace(requests=[], fail_hosts=set())

    def handler(request):
        state.requests.append(request)
        if request.url.host in state.fail_hosts:
            raise httpx.ConnectError("connection refused", request=request)
        return httpx.Response(200, json=COMPLETION)

    real_openai = llm.OpenAI

    def openai_factory(**kwargs):
        return real_openai(http_client=httpx.Client(transport=httpx.MockTransport(handler)), max_retries=0, **kwargs)

    monkeypatch.setattr(llm, "OpenAI", openai_factory)
    return state


def test_local_request_on_the_wire(wire):
    response, provider = chat(MESSAGES, ["confidential"], tools=TOOLS)
    assert provider == "local" and response.choices[0].message.content == "4"
    (request,) = wire.requests
    assert str(request.url) == "http://localhost:8000/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer not-needed"
    body = json.loads(request.content)
    assert body["model"] == "bonsai-2-27b" and body["messages"] == MESSAGES and body["tools"] == TOOLS


def test_cloud_request_on_the_wire(wire):
    chat(MESSAGES, ["public"])
    (request,) = wire.requests
    assert str(request.url) == "https://api.openai.com/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer sk-test"
    assert json.loads(request.content)["model"] == "gpt-test"


def test_outage_on_the_wire_never_reaches_openai(wire):
    wire.fail_hosts = {"localhost"}
    with pytest.raises(LLMUnavailable):
        chat(MESSAGES, ["confidential"])
    assert {r.url.host for r in wire.requests} == {"localhost"}
