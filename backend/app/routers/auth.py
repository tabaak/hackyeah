"""1. Auth and profile. Owners: Vitya / Max."""
from fastapi import APIRouter

from app.deps import not_implemented
from app.schemas.auth import LoginRequest, LoginResponse, Me, MeUpdate, Organization, OrganizationUpdate

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest):
    """Alternative: Supabase Auth SDK directly on the frontend. Open: Google Sign In vs email/password."""
    not_implemented()


@router.get("/me", response_model=Me)
def get_me():
    not_implemented()


@router.put("/me", response_model=Me)
def update_me(body: MeUpdate):
    not_implemented()


@router.get("/organization", response_model=Organization)
def get_organization():
    not_implemented()


@router.put("/organization", response_model=Organization)
def replace_organization(body: OrganizationUpdate):
    not_implemented()


@router.patch("/organization", response_model=Organization)
def update_organization(body: OrganizationUpdate):
    not_implemented()
