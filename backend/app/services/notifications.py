from app.config import settings
from app.db import get_db
from app.services import push
from app.services.timeutil import now, to_ms


def notify(org_id: str, kind: str, title: str, severity: str, mention_id: str | None, roles: tuple[str, ...] | None = None,
           user_ids: list[str] | None = None) -> None:
    """Fan out one notification per recipient (read state is per user); critical ones also go to their phones."""
    db = get_db()
    if user_ids is None:
        q = db.table("profiles").select("user_id").eq("organization_id", org_id)
        if roles:
            q = q.in_("role", list(roles))
        user_ids = [r["user_id"] for r in q.execute().data]
    rows = [
        {"organization_id": org_id, "user_id": uid, "mention_id": mention_id, "kind": kind, "title": title[:200], "severity": severity}
        for uid in user_ids
    ]
    if rows:
        db.table("notifications").insert(rows).execute()
        push.send(user_ids, kind, title, mention_id)


def notify_high_mentions(org_id: str, mentions: list[dict]) -> None:
    cutoff = to_ms(now()) - settings.notify_max_age_hours * 3_600_000
    for m in mentions:
        # Loaded history (old articles) must not raise alarms or phone pushes
        if m["severity"] == "high" and (m.get("published_at") is None or to_ms(m["published_at"]) >= cutoff):
            notify(org_id, "critical_mention", m["text"], "high", m["id"])
