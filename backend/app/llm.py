"""LLM access with server-side routing by data classification.

Two OpenAI-compatible connections:
  cloud  - OPENAI_*       only when every piece of context is `public`
  local  - LOCAL_LLM_*    required as soon as any context is internal/confidential/restricted

The server picks the connection from the labels of the *whole* context (documents, history, derived
text). If the local model is unreachable, closed tasks fail; they are never retried on the cloud.

LLM_FORCE=cloud is a development override: with a cloud key and model it sends *every* label, closed data
included, to the cloud. Never set it where real internal/confidential/restricted documents are processed.
"""
from collections.abc import Iterable
from functools import lru_cache
from typing import Literal

from openai import APIConnectionError, APITimeoutError, OpenAI

from app.config import settings
from app.schemas.common import Classification

Provider = Literal["cloud", "local"]


class LLMUnavailable(RuntimeError):
    """The required provider is not configured or cannot be reached."""


def pick_provider(classifications: Iterable[Classification | str]) -> Provider:
    """Only `public` context (or an explicitly empty list) may go to the cloud; anything else stays local."""
    labels = {Classification(c) for c in classifications}
    cloud_ready = bool(settings.openai_api_key and settings.openai_model)
    if settings.llm_force == "local":
        return "local"
    if settings.llm_force == "cloud" and cloud_ready:
        return "cloud"
    if labels - {Classification.public}:
        return "local"
    return "cloud" if cloud_ready else "local"


@lru_cache
def _client(provider: Provider) -> OpenAI:
    if provider == "cloud":
        if not settings.openai_api_key:
            raise LLMUnavailable("OPENAI_API_KEY is not set")
        return OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url, timeout=settings.llm_timeout_s)
    return OpenAI(api_key=settings.local_llm_api_key, base_url=settings.local_llm_base_url, timeout=settings.llm_timeout_s)


def model_for(provider: Provider) -> str:
    return settings.openai_model if provider == "cloud" else settings.local_llm_model


def chat(messages: list[dict], classifications: Iterable[Classification | str], **kwargs):
    """Run a chat completion on the provider chosen from `classifications`.

    Returns (response, provider) so callers can record which model handled the request (audit/Control Console).
    Extra kwargs (tools, temperature, max_tokens, ...) pass through to the OpenAI SDK.
    """
    provider = pick_provider(classifications)
    try:
        response = _client(provider).chat.completions.create(model=model_for(provider), messages=messages, **kwargs)
    except (APIConnectionError, APITimeoutError) as e:
        raise LLMUnavailable(f"{provider} LLM unreachable: {e}") from e
    return response, provider
