"""OpenAI-compatible chat + embeddings. Every caller has a deterministic fallback, so None means "use it"."""
import json
import logging
import re

import httpx

from app.config import settings

log = logging.getLogger(__name__)
EMBEDDING_DIM = 1536


def _headers(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"} if key else {}


def chat_json(system: str, user: str, max_tokens: int = 800) -> dict | None:
    """One chat completion that must return a JSON object. Returns None on any failure."""
    if not settings.llm_base_url:
        return None
    try:
        r = httpx.post(
            f"{settings.llm_base_url}/chat/completions",
            headers=_headers(settings.llm_api_key),
            json={
                "model": settings.llm_model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "temperature": 0.2,
                "max_tokens": max_tokens,
            },
            timeout=settings.llm_timeout_s,
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"] or ""
    except Exception as e:  # network, HTTP, or unexpected shape
        log.warning("LLM unavailable, using fallback: %s", e)
        return None
    # Models often wrap JSON in prose or ``` fences: take the outermost object.
    m = re.search(r"\{.*\}", content, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def embed(texts: list[str]) -> list[list[float]] | None:
    """Embeddings for texts, or None when not configured / failed / wrong dimension."""
    if not settings.embedding_base_url or not texts:
        return None
    try:
        r = httpx.post(
            f"{settings.embedding_base_url}/embeddings",
            headers=_headers(settings.embedding_api_key),
            json={"model": settings.embedding_model, "input": texts},
            timeout=60,
        )
        r.raise_for_status()
        vectors = [d["embedding"] for d in sorted(r.json()["data"], key=lambda d: d["index"])]
    except Exception as e:
        log.warning("Embeddings unavailable, using keyword retrieval: %s", e)
        return None
    if len(vectors) != len(texts) or any(len(v) != EMBEDDING_DIM for v in vectors):
        log.warning("Embedding model must return %d dims; ignoring vectors", EMBEDDING_DIM)
        return None
    return vectors


def vector_literal(v: list[float]) -> str:
    """pgvector text format, accepted by PostgREST for vector columns and RPC args."""
    return "[" + ",".join(f"{x:.7g}" for x in v) + "]"
