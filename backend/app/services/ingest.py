"""Writing mentions: dedup on (company_id, platform, external_id), analysis, notifications."""
import logging

from postgrest.exceptions import APIError

from app.db import get_db
from app.services import analysis, retrieval
from app.services.notifications import notify_high_mentions


log = logging.getLogger(__name__)
MEDIA_COLUMNS = ("avatar_url", "media_urls")  # added by migration 20261003210000_mention_media.sql
LOOKUP_CHUNK = 20  # external ids per "already stored?" query: they travel in the URL, and article links are long
INSERT_CHUNK = 100  # rows per upsert request


def _upsert(rows: list[dict]) -> list[dict]:
    return (
        get_db().table("mentions")
        .upsert(rows, on_conflict="company_id,platform,external_id", ignore_duplicates=True)
        .execute().data
    )


def insert_mentions(company: dict, rows: list[dict]) -> list[dict]:
    """Insert pre-analysed rows; duplicates are skipped. Returns the rows actually inserted."""
    if not rows:
        return []
    for r in rows:
        r["company_id"] = company["id"]
        r["organization_id"] = company["organization_id"]
    inserted: list[dict] = []
    for i in range(0, len(rows), INSERT_CHUNK):
        chunk = rows[i:i + INSERT_CHUNK]
        try:
            inserted += _upsert(chunk)
        except APIError as e:
            if not any(c in str(e) for c in MEDIA_COLUMNS):
                raise
            log.warning("mentions has no avatar_url/media_urls columns yet: run the media migration. Saving without them.")
            inserted += _upsert([{k: v for k, v in r.items() if k not in MEDIA_COLUMNS} for r in chunk])
    notify_high_mentions(company["organization_id"], inserted)
    return inserted


def analyse_and_insert(company: dict, items: list[dict]) -> list[dict]:
    """Items need platform, external_id, text, published_at; optional author, handle, url, reach, lang."""
    existing = set()
    ids = [i["external_id"] for i in items]
    for start in range(0, len(ids), LOOKUP_CHUNK):
        found = (
            get_db().table("mentions").select("platform, external_id").eq("company_id", company["id"])
            .in_("external_id", ids[start:start + LOOKUP_CHUNK]).execute().data
        )
        existing |= {(r["platform"], r["external_id"]) for r in found}
    rows = []
    for item in items:
        if (item["platform"], item["external_id"]) in existing:
            continue  # skip the LLM call for known mentions
        hits = retrieval.search(company["id"], item["text"], limit=5)
        a = analysis.assess(company, item["text"], item.get("reach", 0), hits)
        rows.append({**item, "severity": a.severity, "verdict": a.verdict, "reason": a.reason, "injection_suspected": a.injection})
    return insert_mentions(company, rows)
