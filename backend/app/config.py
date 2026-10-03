import os
from pathlib import Path

from dotenv import load_dotenv

# backend/.env (gitignored); real environment variables take precedence.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


class Settings:
    supabase_url: str = os.getenv("SUPABASE_URL", "").rstrip("/")
    # Secret / service_role key: the API is the only trusted writer and bypasses RLS,
    # so every query must filter by the caller's organization_id.
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    supabase_jwt_secret: str = os.getenv("SUPABASE_JWT_SECRET", "")
    cors_origins: list[str] = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]

    # OpenAI-compatible chat endpoint; local Bonsai server by default (port 8001: the API itself runs on 8000).
    # Unreachable or unset -> deterministic fallbacks (template drafts, heuristic analysis).
    llm_base_url: str = os.getenv("LLM_BASE_URL", "http://localhost:8001/v1").rstrip("/")
    llm_model: str = os.getenv("LLM_MODEL", "bonsai-2-27b")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_timeout_s: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))

    # OpenAI-compatible embeddings; must return 1536 dims (document_chunks.embedding).
    # Unset -> keyword retrieval instead of vector search.
    embedding_base_url: str = os.getenv("EMBEDDING_BASE_URL", "").rstrip("/")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    embedding_api_key: str = os.getenv("EMBEDDING_API_KEY", "")

    serper_api_key: str = os.getenv("SERPER_API_KEY", "")

    # Demo data: seed sample mentions for every new company, and optionally add one every N seconds.
    demo_seed: bool = os.getenv("DEMO_SEED", "true").lower() == "true"
    demo_live_interval_s: int = _int("DEMO_LIVE_INTERVAL_SECONDS", 0)


settings = Settings()
