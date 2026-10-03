"""1. Authentication and user."""
from fastapi import APIRouter

from app.deps import not_implemented
from app.schemas.auth import LoginRequest, LoginResponse, Me

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest):
    """Exchanges a Google Sign-in token for a Supabase session."""
    not_implemented()


@router.post("/auth/logout", status_code=204)
def logout():
    not_implemented()


@router.get("/me", response_model=Me)
def get_me():
    not_implemented()
