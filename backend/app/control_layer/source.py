"""Read-only bridge. Never import legacy derived reasons, document joins or private metadata."""
from urllib.parse import urlsplit

from .models import Evidence

REPORTERS = {"reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "ft.com", "bloomberg.com",
             "wsj.com", "sec.gov", "europa.eu", "justice.gov"}


class SupabaseSource:
    def company(self, org, company_id):
        from app.db import get_db
        rows = get_db().table("companies").select("id,name,aliases,website,country,sector").eq(
            "organization_id", org).eq("id", company_id).execute().data
        return rows[0] if rows else None

    def mentions(self, org, company_id, since, limit=100):
        from app.db import get_db
        rows = get_db().table("mentions").select("id,text,url,published_at,platform").eq(
            "organization_id", org).eq("company_id", company_id).gte(
            "published_at", since).order("published_at", desc=True).limit(limit + 1).execute().data
        evidence = []
        for row in rows[:limit]:
            url = row.get("url") or ""
            host = urlsplit(url).hostname or ""
            # This identifies publisher independence, not the truth of an article's claims.
            independent = row.get("platform") == "news" and any(host == d or host.endswith("." + d) for d in REPORTERS)
            evidence.append(Evidence(id=row["id"], content=row["text"], classification="public",
                                     origin="public_feed", source_url=url, published_at=row["published_at"],
                                     independent=independent))
        return evidence, len(rows) > limit
