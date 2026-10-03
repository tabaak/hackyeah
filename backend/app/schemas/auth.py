from pydantic import BaseModel

from app.schemas.common import Role


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class Me(BaseModel):
    id: str
    email: str
    role: Role
    organization_id: str
    display_name: str | None = None


class MeUpdate(BaseModel):
    display_name: str | None = None


class Organization(BaseModel):
    id: str
    name: str
    aliases: list[str] = []
    sector: str  # bank | defence
    monitoring_topics: list[str] = []


class OrganizationUpdate(BaseModel):
    name: str | None = None
    aliases: list[str] | None = None
    sector: str | None = None
    monitoring_topics: list[str] | None = None
