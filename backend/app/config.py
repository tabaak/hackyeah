import os
from pathlib import Path

from dotenv import load_dotenv

# Repo-root .env (git-ignored). Real environment variables take precedence.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def _env(name: str, default: str = "") -> str:
    """Empty values (e.g. `OPENAI_MODEL=` copied from .env.example) count as unset."""
    return os.getenv(name) or default


class Settings:
    supabase_url: str = _env("SUPABASE_URL").rstrip("/")  # deps.py appends /auth/v1
    supabase_jwt_secret: str = _env("SUPABASE_JWT_SECRET")
    serper_api_key: str = _env("SERPER_API_KEY")
    apify_token: str = _env("APIFY_TOKEN")

    # Cloud LLM: used only for tasks whose whole context is `public`.
    openai_api_key: str = _env("OPENAI_API_KEY") or _env("OPENAI_KEY")
    openai_base_url: str = _env("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_model: str = _env("OPENAI_MODEL")

    # Local LLM: required for internal/confidential/restricted context. Any OpenAI-compatible server
    # (default: local-models/server/server.py serving Bonsai).
    local_llm_base_url: str = _env("LOCAL_LLM_BASE_URL", "http://localhost:8000/v1")
    local_llm_model: str = _env("LOCAL_LLM_MODEL", "bonsai-2-27b")
    local_llm_api_key: str = _env("LOCAL_LLM_API_KEY", "not-needed")

    # Set to "local" to send everything (including public) to the local model, e.g. with no cloud key.
    llm_force: str = _env("LLM_FORCE")
    llm_timeout_s: float = float(_env("LLM_TIMEOUT_S", "120"))


settings = Settings()
