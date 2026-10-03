from datetime import datetime, timezone

from app.routers.analytics import day_buckets

TODAY = datetime(2026, 10, 3, 14, 30, tzinfo=timezone.utc)


def row(published_at, severity="low"):
    return {"published_at": published_at, "severity": severity}


def test_buckets_cover_the_range_oldest_first():
    out = day_buckets([], 7, TODAY)
    assert [b.day for b in out] == ["2026-09-27", "2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01", "2026-10-02", "2026-10-03"]
    assert all((b.low, b.medium, b.high) == (0, 0, 0) for b in out)
    assert len(day_buckets([], 30, TODAY)) == 30


def test_counts_by_severity_and_utc_day():
    rows = [
        row("2026-10-03T00:00:00+00:00", "high"),
        row("2026-10-03T23:59:59Z", "high"),
        row("2026-10-03T10:00:00+00:00", "low"),
        row("2026-10-02T12:00:00+02:00", "medium"),  # 10:00 UTC on the 2nd
        row("2026-10-02T01:00:00+02:00", "medium"),  # 23:00 UTC on the 1st
    ]
    by_day = {b.day: (b.low, b.medium, b.high) for b in day_buckets(rows, 7, TODAY)}
    assert by_day["2026-10-03"] == (1, 0, 2)
    assert by_day["2026-10-02"] == (0, 1, 0)
    assert by_day["2026-10-01"] == (0, 1, 0)


def test_rows_outside_the_range_are_ignored():
    assert sum(b.low for b in day_buckets([row("2026-09-26T23:59:59+00:00")], 7, TODAY)) == 0
    assert sum(b.low for b in day_buckets([row("2026-10-04T00:00:00+00:00")], 7, TODAY)) == 0


def test_json_is_camel_case():
    assert day_buckets([], 7, TODAY)[0].model_dump(by_alias=True) == {"day": "2026-09-27", "low": 0, "medium": 0, "high": 0}
