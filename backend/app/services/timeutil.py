from datetime import datetime, timedelta, timezone


def now() -> datetime:
    return datetime.now(timezone.utc)


def to_ms(value: str | datetime | None) -> int | None:
    """timestamptz (ISO string from PostgREST) -> Unix ms, the API's time format."""
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp() * 1000)


def from_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat()


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def ago(**kw) -> str:
    return iso(now() - timedelta(**kw))
