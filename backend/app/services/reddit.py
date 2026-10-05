"""Reddit posts and comments through PullPush (platform = reddit): free, no key, keyword search across all of Reddit.

Reddit's own API needs an approved app, and its .json / search.rss endpoints answer 403 to anonymous requests.
PullPush (the open successor of Pushshift) archives Reddit with a lag of about a day, so this source finds
yesterday's threads, not the last minute; the `days` window covers that lag, and ingest skips what is already stored.
"""
import logging
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from app.services import relevance
from app.services.timeutil import iso, now

log = logging.getLogger(__name__)
SEARCH_URL = "https://api.pullpush.io/reddit/search/{kind}/"
PAUSE_S = 4  # a free community service: stay well under its per-minute limit (it answers 429 to bursts)
TEXT_CHARS = 1000
IMAGE_HOSTS = ("i.redd.it", "i.imgur.com")
GONE = {"[deleted]", "[removed]", ""}


def to_item(row: dict, kind: str) -> dict | None:
    """PullPush submission or comment -> ingestion row; None for deleted or removed content."""
    author = row.get("author") or ""
    if kind == "submission":
        body = (row.get("selftext") or "").strip()
        text = " — ".join(x for x in (row.get("title", "").strip(), "" if body in GONE else body[:TEXT_CHARS]) if x)
        link = row.get("url") or ""
        media = [link] if urlparse(link).netloc in IMAGE_HOSTS else []
        reach, fullname = int(row.get("score") or 0) + int(row.get("num_comments") or 0), f"t3_{row['id']}"
    else:
        text = (row.get("body") or "").strip()
        if text in GONE:
            return None
        text, media, reach, fullname = text[:TEXT_CHARS], [], int(row.get("score") or 0), f"t1_{row['id']}"
    if author in GONE or not text:
        return None
    return {
        "platform": "reddit",
        "external_id": fullname,
        "url": f"https://www.reddit.com{row['permalink']}" if row.get("permalink") else None,
        "author": f"r/{row.get('subreddit', '')}",
        "handle": f"u/{author}",
        "text": text,
        "published_at": iso(datetime.fromtimestamp(float(row["created_utc"]), timezone.utc)),
        "reach": max(reach, 0),
        "avatar_url": None,
        "media_urls": media,
    }


def fetch(company: dict, queries: list[str], *, days: int = 3, client: httpx.Client | None = None,
          pause_s: float = PAUSE_S) -> list[dict]:
    """Posts and comments of the last `days` days naming the company, newest first per query.
    Rate-limited (429): returns what it has; the next scheduled run picks up the rest."""
    after = int(now().timestamp()) - days * 86_400
    items, seen = [], set()
    with client or httpx.Client(timeout=30) as c:
        for i, (q, kind) in enumerate((q, kind) for q in queries for kind in ("submission", "comment")):
            if i:
                time.sleep(pause_s)
            r = c.get(SEARCH_URL.format(kind=kind), params={"q": q, "size": 100, "sort": "desc", "after": after})
            if r.status_code == 429:
                log.warning("PullPush rate-limited us; skipping the rest of this Reddit run")
                break
            r.raise_for_status()
            for row in r.json().get("data", []):
                item = to_item(row, kind)
                if not item or item["external_id"] in seen or not relevance.mentions_company(item["text"], company):
                    continue
                seen.add(item["external_id"])
                items.append(item)
    return items
