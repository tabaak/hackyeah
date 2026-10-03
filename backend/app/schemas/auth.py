from app.schemas.common import CamelModel, Role


class Me(CamelModel):
    name: str
    email: str
    role: Role


class CurrentUser(Me):
    """Authenticated caller as resolved from the Supabase JWT (internal; `/me` returns only `Me`)."""

    id: str
    organization_id: str
