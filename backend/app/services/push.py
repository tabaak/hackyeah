"""Mobile push through the Expo push service (APNs/FCM behind one API); tokens come from the mobile app."""
import logging

import httpx

from app.config import settings
from app.db import get_db

log = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
PUSHED_KINDS = {"critical_mention"}  # the rest stay in-app only
KIND_TITLE = {"critical_mention": "Critical mention"}
BATCH = 100  # Expo accepts at most 100 messages per request
BODY_MAX = 180  # lock screens show ~2-4 lines

_http = httpx.Client(timeout=10)


def send(user_ids: list[str], kind: str, body: str, mention_id: str | None) -> None:
    """Best effort: a push failure is logged and never fails the caller (the in-app notification is already stored)."""
    if kind not in PUSHED_KINDS or not user_ids:
        return
    try:
        db = get_db()
        tokens = [r["token"] for r in db.table("push_tokens").select("token").in_("user_id", user_ids).execute().data]
        text = body if len(body) <= BODY_MAX else body[: BODY_MAX - 1] + "…"
        messages = [
            {
                "to": t, "title": KIND_TITLE[kind], "body": text, "data": {"kind": kind, "mentionId": mention_id},
                "sound": "default", "priority": "high", "channelId": "critical",
            }
            for t in tokens
        ]
        headers = {"Authorization": f"Bearer {settings.expo_access_token}"} if settings.expo_access_token else {}
        for i in range(0, len(messages), BATCH):
            batch = messages[i:i + BATCH]
            res = _http.post(EXPO_PUSH_URL, json=batch, headers=headers)
            res.raise_for_status()
            # Tickets come back in message order; DeviceNotRegistered = app uninstalled or push disabled
            gone = [m["to"] for m, t in zip(batch, res.json()["data"])
                    if t.get("status") == "error" and t.get("details", {}).get("error") == "DeviceNotRegistered"]
            if gone:
                db.table("push_tokens").delete().in_("token", gone).execute()
    except Exception:
        log.warning("push delivery failed", exc_info=True)
