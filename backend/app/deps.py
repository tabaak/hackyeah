from fastapi import HTTPException, status

from app.schemas.auth import Me


def not_implemented() -> None:
    """Every endpoint is a stub until its owner implements it."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Not implemented")


def get_current_user() -> Me:
    """Validate `Authorization: Bearer <supabase_jwt>`; role and organization come from the server, not the client."""
    not_implemented()


def require_compliance() -> Me:
    """Allow only the `compliance` role (confidential approvals)."""
    not_implemented()
