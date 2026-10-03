import os

# Deterministic settings for unit tests (set before app.config is imported).
os.environ.setdefault("SUPABASE_URL", "https://ref.supabase.co")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-test-secret-test-secret-xx")
os.environ["LLM_BASE_URL"] = ""
os.environ["EMBEDDING_BASE_URL"] = ""
os.environ["DEMO_LIVE_INTERVAL_SECONDS"] = "0"
