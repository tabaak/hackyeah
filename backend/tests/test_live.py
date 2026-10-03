"""Real services with the real .env (run with --live). Costs: 1 Serper credit; a few tokens on OpenAI if enabled."""
import json
import time

import httpx
import pytest

from app.config import settings
from app.llm import LLMUnavailable, chat
from app.sources.serper import MOCK_COMPANY, search_news

pytestmark = pytest.mark.live
QUESTION = [{"role": "user", "content": "Answer with the number only: 2+2"}]
TOOLS = [{"type": "function", "function": {
    "name": "search_documents", "description": "Search the organisation's documents.",
    "parameters": {"type": "object", "required": ["query"],
                   "properties": {"query": {"type": "string"}, "max_results": {"type": "integer"}}}}}]


def test_serper_finds_recent_news():
    if not settings.serper_api_key:
        pytest.skip("SERPER_API_KEY is not set")
    found = search_news(MOCK_COMPANY, "live-check", max_queries=1)
    assert found
    now = time.time() * 1000
    for m in found:
        assert m.url.startswith("http") and m.text and m.author
        assert now - 90 * 86_400_000 < m.at <= now + 60_000


def local_chat(messages, **kwargs):
    try:
        return chat(messages, ["confidential"], **kwargs)
    except LLMUnavailable:
        pytest.skip(f"local LLM is not reachable at {settings.local_llm_base_url}")


def test_local_llm_answers():
    response, provider = local_chat(QUESTION, max_tokens=10)
    assert provider == "local" and response.choices[0].message.content.strip() == "4"


def test_local_llm_calls_tools():
    response, _ = local_chat([
        {"role": "system", "content": "You are an investigation agent. Use tools to look things up."},
        {"role": "user", "content": "Find documents about ATM maintenance, at most 3 results."}], tools=TOOLS, max_tokens=200)
    call = response.choices[0].message.tool_calls[0]
    assert call.function.name == "search_documents" and json.loads(call.function.arguments).get("max_results") == 3


def test_cloud_llm_answers():
    if not (settings.openai_api_key and settings.openai_model):
        pytest.skip("cloud LLM is disabled: OPENAI_API_KEY and OPENAI_MODEL must both be set")
    response, provider = chat(QUESTION, ["public"])
    assert provider == "cloud" and "4" in response.choices[0].message.content


def test_supabase_jwks_is_reachable():
    if not settings.supabase_url:
        pytest.skip("SUPABASE_URL is not set")
    r = httpx.get(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json", timeout=10)
    assert r.status_code == 200 and isinstance(r.json().get("keys"), list)
