from functools import lru_cache

from fastapi import HTTPException, status
from supabase import Client, create_client

from app.config import settings

DOCUMENTS_BUCKET = "documents"


@lru_cache
def get_db() -> Client:
    """Service-role client. Bypasses RLS: callers must scope every query by organization_id."""
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not configured")
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def not_found(what: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{what} not found")
