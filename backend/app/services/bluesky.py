"""Bluesky post search (platform = bluesky). Free, no key, posts are searchable within minutes: the live source.

public.api.bsky.app answers 403 to search; api.bsky.app serves it anonymously (rate limit ~3000 requests / 5 min / IP).
"""
from datetime import timedelta

import httpx

from app.services import relevance
from app.services.timeutil import iso, now

SEARCH_URL = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"
MAX_IMAGES = 6


def to_item(post: dict) -> dict:
    handle = post["author"]["handle"]
    images = [i.get("fullsize") or i.get("thumb") for i in (post.get("embed") or {}).get("images") or []]
    return {
        "platform": "bluesky",
        "external_id": post["uri"],
        "url": f"https://bsky.app/profile/{handle}/post/{post['uri'].rsplit('/', 1)[-1]}",
        "author": post["author"].get("displayName") or handle,
        "handle": handle,
        "text": post["record"].get("text") or "",
        "published_at": post["record"].get("createdAt") or post["indexedAt"],
        "reach": sum(int(post.get(k) or 0) for k in ("likeCount", "repostCount", "replyCount", "quoteCount")),
        "avatar_url": post["author"].get("avatar"),
        "media_urls": [u for u in images if u][:MAX_IMAGES],
    }


def fetch(company: dict, queries: list[str], *, days: int = 2, client: httpx.Client | None = None) -> list[dict]:
    """Newest posts of the last `days` days naming the company; already stored ones are skipped later by ingest."""
    items, seen = [], set()
    since = iso(now() - timedelta(days=days))
    with client or httpx.Client(timeout=20) as c:
        for q in queries:
            r = c.get(SEARCH_URL, params={"q": q, "sort": "latest", "limit": 100, "since": since})
            r.raise_for_status()
            for post in r.json().get("posts", []):
                item = to_item(post)
                if item["external_id"] in seen or not item["text"] or not relevance.mentions_company(item["text"], company):
                    continue
                seen.add(item["external_id"])
                items.append(item)
    return items
