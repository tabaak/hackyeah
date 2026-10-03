from app.schemas.common import CamelModel, Role


class LoginRequest(CamelModel):
    id_token: str  # Google Sign-in token, exchanged via Supabase


class LoginResponse(CamelModel):
    access_token: str
    token_type: str = "bearer"


class Me(CamelModel):
    name: str
    email: str
    role: Role
