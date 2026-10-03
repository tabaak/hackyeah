import os


class Settings:
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_jwt_secret: str = os.getenv("SUPABASE_JWT_SECRET", "")
    # OpenAI-compatible endpoint; local Bonsai server by default (local-models/server/server.py)
    llm_base_url: str = os.getenv("LLM_BASE_URL", "http://localhost:8000/v1")
    llm_model: str = os.getenv("LLM_MODEL", "bonsai-2-27b")
    serper_api_key: str = os.getenv("SERPER_API_KEY", "")


settings = Settings()
