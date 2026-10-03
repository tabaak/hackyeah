"""7. Push: the mobile app registers its Expo push token after sign-in and removes it on sign-out."""
from fastapi import APIRouter, Depends

from app.db import get_db
from app.deps import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.push import PushToken
from app.services.timeutil import iso, now

router = APIRouter(prefix="/push-tokens", tags=["notifications"])


@router.post("", status_code=204)
def register(body: PushToken, user: CurrentUser = Depends(get_current_user)):
    """Upsert by token: a device that signs in to another account moves to that account."""
    get_db().table("push_tokens").upsert(
        {"token": body.token, "user_id": user.id, "organization_id": user.organization_id, "platform": body.platform,
         "updated_at": iso(now())},
        on_conflict="token",
    ).execute()


@router.delete("/{token}", status_code=204)
def unregister(token: str, user: CurrentUser = Depends(get_current_user)):
    get_db().table("push_tokens").delete().eq("token", token).eq("user_id", user.id).execute()
