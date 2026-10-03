"""1. Current user. Sign-in itself is Google OAuth via Supabase Auth in the browser; the API only verifies the JWT."""
from fastapi import APIRouter, Depends

from app.deps import get_current_user
from app.schemas.auth import CurrentUser, Me

router = APIRouter(tags=["auth"])


@router.get("/me", response_model=Me)
def get_me(user: CurrentUser = Depends(get_current_user)):
    return user
