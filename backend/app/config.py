import os
from pathlib import Path

from dotenv import load_dotenv

# backend/.env first, then the repo-root .env (both gitignored); real environment variables take precedence.
BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent / ".env")


def _env(name: str, default: str = "") -> str:
    """Empty values (e.g. `OPENAI_MODEL=` copied from .env.example) count as unset."""
    return os.getenv(name) or default


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


class Settings:
    supabase_url: str = _env("SUPABASE_URL").rstrip("/")  # deps.py appends /auth/v1
    # Secret / service_role key: the API is the only trusted writer and bypasses RLS,
    # so every query must filter by the caller's organization_id.
    supabase_service_role_key: str = _env("SUPABASE_SERVICE_ROLE_KEY")
    supabase_jwt_secret: str = _env("SUPABASE_JWT_SECRET")
    cors_origins: list[str] = [o.strip() for o in _env("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]

    # OpenAI-compatible chat endpoint for analysis and drafts; local Bonsai server by default (port 8001: the API
    # itself runs on 8000). Explicitly empty -> deterministic fallbacks (template drafts, heuristic analysis).
    llm_base_url: str = os.getenv("LLM_BASE_URL", "http://localhost:8001/v1").rstrip("/")
    llm_model: str = _env("LLM_MODEL", "bonsai-2-27b")
    llm_api_key: str = _env("LLM_API_KEY")
    llm_timeout_s: float = float(_env("LLM_TIMEOUT_SECONDS") or _env("LLM_TIMEOUT_S", "30"))

    # OpenAI-compatible embeddings; must return 1536 dims (document_chunks.embedding). Unset -> keyword retrieval.
    embedding_base_url: str = _env("EMBEDDING_BASE_URL").rstrip("/")
    embedding_model: str = _env("EMBEDDING_MODEL", "text-embedding-3-small")
    embedding_api_key: str = _env("EMBEDDING_API_KEY")

    # Classification-routed chat (app/llm.py): only `public` context may use the cloud model.
    openai_api_key: str = _env("OPENAI_API_KEY") or _env("OPENAI_KEY")
    openai_base_url: str = _env("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_model: str = _env("OPENAI_MODEL")
    # Local model for internal/confidential/restricted context; defaults to the LLM_* server above.
    local_llm_base_url: str = _env("LOCAL_LLM_BASE_URL", llm_base_url or "http://localhost:8001/v1")
    local_llm_model: str = _env("LOCAL_LLM_MODEL", llm_model)
    local_llm_api_key: str = _env("LOCAL_LLM_API_KEY", llm_api_key or "not-needed")
    # Set to "local" to send everything (including public) to the local model, e.g. with no cloud key.
    llm_force: str = _env("LLM_FORCE")

    serper_api_key: str = _env("SERPER_API_KEY")
    apify_token: str = _env("APIFY_TOKEN")

    # Demo data: seed sample mentions for every new company, and optionally add one every N seconds.
    demo_seed: bool = _env("DEMO_SEED", "true").lower() == "true"
    demo_live_interval_s: int = _int("DEMO_LIVE_INTERVAL_SECONDS", 0)


settings = Settings()
