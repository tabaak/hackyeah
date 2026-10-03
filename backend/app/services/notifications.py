from app.db import get_db


def notify(org_id: str, kind: str, title: str, severity: str, mention_id: str | None, roles: tuple[str, ...] | None = None,
           user_ids: list[str] | None = None) -> None:
    """Fan out one notification per recipient (read state is per user)."""
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


def notify_high_mentions(org_id: str, mentions: list[dict]) -> None:
    for m in mentions:
        if m["severity"] == "high":
            notify(org_id, "critical_mention", m["text"], "high", m["id"])
