from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.schemas.auth import CurrentUser
from app.schemas.common import Role

bearer = HTTPBearer(auto_error=False)

# Asymmetric Supabase signing keys; HS256 only for projects still on the legacy shared secret.
ASYMMETRIC_ALGS = ("RS256", "ES256")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json", cache_keys=True)


def _decode(token: str) -> dict:
    alg = jwt.get_unverified_header(token).get("alg")
    if alg == "HS256":
        if not settings.supabase_jwt_secret:
            raise _unauthorized("HS256 tokens are not accepted")
        key = settings.supabase_jwt_secret
    elif alg in ASYMMETRIC_ALGS:
        if not settings.supabase_url:
            raise _unauthorized("SUPABASE_URL is not configured")
        key = _jwks_client().get_signing_key_from_jwt(token).key
    else:
        raise _unauthorized("Unsupported token algorithm")

    return jwt.decode(
        token,
        key,
        algorithms=[alg],
        audience="authenticated",
        issuer=f"{settings.supabase_url}/auth/v1" if settings.supabase_url else None,
        options={"require": ["exp", "sub"]},
    )


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> CurrentUser:
    """Validate `Authorization: Bearer <supabase_jwt>`; role and organization come from token-hook claims, not the client."""
    if creds is None:
        raise _unauthorized("Missing bearer token")
    try:
        claims = _decode(creds.credentials)
    except jwt.PyJWTError:
        raise _unauthorized("Invalid or expired token")

    # Google is the only allowed sign-in method (also enforced in Supabase Auth config and the sign-up trigger).
    if claims.get("app_metadata", {}).get("provider") != "google":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only Google sign-in is allowed")

    role, org = claims.get("user_role"), claims.get("organization_id")
    if role not in Role._value2member_map_ or not org:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User profile is not provisioned")

    meta = claims.get("user_metadata", {})
    return CurrentUser(
        id=claims["sub"],
        organization_id=org,
        name=meta.get("full_name") or meta.get("name") or "",
        email=claims.get("email", ""),
        role=role,
    )


def require_compliance(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Allow only the `compliance` role (confidential approvals)."""
    if user.role != Role.compliance:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Compliance role required")
    return user
