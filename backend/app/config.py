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
    # "cloud" (development only) sends everything, closed data included, to the OPENAI_* model.
    llm_force: str = _env("LLM_FORCE")

    serper_api_key: str = _env("SERPER_API_KEY")
    apify_token: str = _env("APIFY_TOKEN")
    # Posts per run, per platform: bounds Apify cost. X is almost free (~$0.00015/post), Facebook ~$0.006.
    apify_limit_x: int = _int("APIFY_LIMIT_X", 50)
    apify_limit_facebook: int = _int("APIFY_LIMIT_FACEBOOK", 30)
    apify_limit_reddit: int = _int("APIFY_LIMIT_REDDIT", 30)  # per query, ~$0.001/post
    apify_max_age_days: int = _int("APIFY_MAX_AGE_DAYS", 30)  # search results can be old; skip posts older than this

    # News volume: Serper returns 10 articles per page (1 credit each); Google News RSS is free, up to 100 per request.
    # Regular runs only look for what is new (cheap); a company's history is loaded once by a deeper "backfill" run.
    serper_pages: int = _int("SERPER_PAGES", 1)
    news_window: str = _env("NEWS_WINDOW", "h")  # Serper window of regular runs: h | d | w | m
    news_backfill_days: int = _int("NEWS_BACKFILL_DAYS", 60)  # how far back the one-time history run goes (RSS, free)
    news_backfill_pages: int = _int("NEWS_BACKFILL_PAGES", 5)  # Serper pages per query over the last month (1 credit each)
    news_rss: bool = _env("NEWS_RSS", "true").lower() == "true"
    # Analyse every item with the LLM (~6 s each). Default: only items with a risk signal; the rest keep the keyword score.
    llm_analyse_all: bool = _env("LLM_ANALYSE_ALL", "false").lower() == "true"

    # Expo push service. Optional: only needed when "enhanced push security" is on for the Expo project.
    expo_access_token: str = _env("EXPO_ACCESS_TOKEN")

    # Scheduler: repeats the collection in the background. Minutes between runs per source, 0 = never.
    # Live defaults; costs per company and run: news ~2 Serper credits (~300/day at 10 min), X ~$0.008 (50 posts, ~$1.1/day),
    # Reddit ~$0.001/post of the last hour, Facebook ~$0.2 (30 posts), Bluesky and Google News RSS free.
    sync_enabled: bool = _env("SYNC_ENABLED", "true").lower() == "true"
    sync_news_minutes: int = _int("SYNC_NEWS_MINUTES", 10)
    sync_x_minutes: int = _int("SYNC_X_MINUTES", 10)
    sync_facebook_minutes: int = _int("SYNC_FACEBOOK_MINUTES", 720)
    sync_reddit_minutes: int = _int("SYNC_REDDIT_MINUTES", 15)
    sync_bluesky_minutes: int = _int("SYNC_BLUESKY_MINUTES", 2)  # free
    sync_startup_delay_s: int = _int("SYNC_STARTUP_DELAY_SECONDS", 120)
    # Critical notifications (and phone pushes) only for mentions this recent: loaded history must not alarm anyone.
    notify_max_age_hours: int = _int("NOTIFY_MAX_AGE_HOURS", 72)

    # Demo data: seed sample mentions for every new company, and optionally add one every N seconds.
    demo_seed: bool = _env("DEMO_SEED", "false").lower() == "true"
    demo_live_interval_s: int = _int("DEMO_LIVE_INTERVAL_SECONDS", 0)


settings = Settings()
