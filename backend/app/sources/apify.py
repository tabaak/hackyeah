"""Social posts (X, Facebook, Threads) through Apify actors -> `Mention` objects.

Each platform is one Apify actor run; its dataset items are mapped to `Mention` with tolerant field lookups,
because actor output schemas differ and change. Actor ids and input fields are defaults: check the actor page in
the Apify Store and adjust `ACTORS` / the `*_input` functions if it complains.

Look at raw answers first (costs Apify credits):
    python -m app.sources.apify x          # or: facebook | threads
Raw dataset items are printed so you can see the real field names.
"""
import hashlib
import json
import sys
import time
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.schemas.common import MentionStatus, Platform, Severity, Verdict
from app.schemas.companies import CompanyDraft
from app.schemas.feed import Mention

APIFY_URL = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"

ACTORS = {
    # xquik: $0.00015/post and usable on the free Apify plan. apidojo/tweet-scraper refuses free-plan runs
    # ("Monthly run limit exceeded per user") and returns only `noResults` rows.
    Platform.x: "xquik/x-tweet-scraper",
    Platform.facebook: "apify/facebook-search-scraper",  # keyword search; alternative: danek/facebook-search-ppr
    # futurizerush: keyword search, ~$0.08 for a 10-post run on the free plan (igview-owner/threads-search-scraper
    # costs about 5x more per post).
    Platform.threads: "futurizerush/meta-threads-scraper",
}


class ApifyError(RuntimeError):
    pass


# Each function returns the list of run inputs for one platform (one actor run per input).
def x_input(company: CompanyDraft, queries: list[str], limit: int) -> list[dict]:
    return [{"searchTerms": queries, "maxItems": limit, "queryType": "Latest"}]


def facebook_input(company: CompanyDraft, queries: list[str], limit: int) -> list[dict]:
    # apify/facebook-search-scraper: `categories` holds the keywords. (danek/facebook-search-ppr instead takes
    # {"query": str, "search_type": "posts", "max_posts": int, "recent_posts": True}, one run per query.)
    return [{"categories": queries, "searchType": "posts", "resultsLimit": limit}]


def threads_input(company: CompanyDraft, queries: list[str], limit: int) -> list[dict]:
    # One run, first query only: the actor bills per post and per run, and `max_posts` (minimum 10) applies per keyword.
    return [{"mode": "search", "keywords": queries[:1], "max_posts": max(limit, 10), "search_filter": "recent"}]


INPUTS = {Platform.x: x_input, Platform.facebook: facebook_input, Platform.threads: threads_input}


def _first(item: dict, *paths: str):
    """First non-empty value among dotted paths ("author.userName")."""
    for path in paths:
        cur = item
        for key in path.split("."):
            cur = cur.get(key) if isinstance(cur, dict) else None
        if cur not in (None, "", []):
            return cur
    return None


def _ms(value, now_ms: int) -> int:
    if isinstance(value, (int, float)):
        return int(value if value > 1e11 else value * 1000)
    if isinstance(value, str):
        for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
            try:
                return int(datetime.strptime(value, fmt).astimezone(timezone.utc).timestamp() * 1000)
            except ValueError:
                pass
        try:
            return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
        except ValueError:
            pass
    return now_ms


def to_mention(item: dict, platform: Platform, company_id: str, now_ms: int) -> Mention | None:
    if item.get("record_type") not in (None, "post"):  # Threads actor can also emit profile rows
        return None
    text = _first(item, "text", "text_content", "fullText", "full_text", "captionText", "caption.text", "caption", "message", "postText", "previewTitle", "content")
    url = _first(item, "url", "postUrl", "post_url", "twitterUrl", "topLevelUrl", "link")
    if not text:
        return None
    handle = _first(item, "author.userName", "author.username", "user.username", "username", "user.id", "pageName.id") or ""
    author = _first(item, "author.name", "user.name", "user.fullName", "pageName.name", "display_name", "username") or handle or platform.value
    reach = sum(
        int(_first(item, *keys) or 0)
        for keys in (("likeCount", "like_count", "likes", "likesCount"),
                     ("retweetCount", "shares", "sharesCount", "repostCount", "repost_count"),
                     ("replyCount", "reply_count", "comments", "commentsCount", "directReplyCount"))
    )
    ident = str(_first(item, "id", "postId", "post_id") or url or text)
    return Mention(
        id=f"{platform.value}_" + hashlib.sha1(f"{company_id}|{ident}".encode()).hexdigest()[:12],
        company_id=company_id,
        platform=platform,
        author=str(author),
        handle=str(handle).lstrip("@"),
        text=str(text).strip(),
        at=_ms(_first(item, "createdAt", "created_at", "timestamp", "time", "takenAtISO", "takenAt", "date"), now_ms),
        severity=Severity.low,  # placeholders until analysis fills them in
        verdict=Verdict.insufficient_evidence,
        reason="",
        reach=reach,
        cluster=None,
        injection=False,
        status=MentionStatus.new,
        url=str(url) if url else None,
    )


def run_actor(platform: Platform, run_input: dict, *, client: httpx.Client | None = None) -> list[dict]:
    """Run the actor and wait for its dataset items (fine for runs under ~5 min)."""
    if not settings.apify_token and client is None:
        raise ApifyError("APIFY_TOKEN is not set")
    own = client is None
    client = client or httpx.Client(timeout=300)
    try:
        r = client.post(
            APIFY_URL.format(actor=ACTORS[platform].replace("/", "~")),
            params={"token": settings.apify_token},
            json=run_input,
        )
        if r.status_code not in (200, 201):
            raise ApifyError(f"Apify {r.status_code}: {r.text[:200]}")
        return r.json()
    finally:
        if own:
            client.close()


def search_posts(
    company: CompanyDraft,
    company_id: str,
    queries: list[str],
    *,
    platforms: tuple[Platform, ...] = (Platform.x, Platform.facebook),  # Threads costs ~$0.7/run: opt in
    limit: int = 30,
    max_age_days: int = 90,
    client: httpx.Client | None = None,
) -> list[Mention]:
    """Posts from the last `max_age_days` days (search results can be old). A failing platform is skipped (stderr), not fatal."""
    now_ms, seen, out = int(time.time() * 1000), set(), []
    for platform in platforms:
        try:
            items = [i for inp in INPUTS[platform](company, queries, limit) for i in run_actor(platform, inp, client=client)]
        except (ApifyError, httpx.HTTPError) as e:
            print(f"[apify] {platform.value} skipped: {e}", file=sys.stderr)
            continue
        for item in items:
            m = to_mention(item, platform, company_id, now_ms)
            if m and m.id not in seen and m.at >= now_ms - max_age_days * 86400_000:
                seen.add(m.id)
                out.append(m)
    return sorted(out, key=lambda m: m.at, reverse=True)


if __name__ == "__main__":
    from app.analysis import negative_queries
    from app.sources.serper import MOCK_COMPANY

    platform = Platform(sys.argv[1] if len(sys.argv) > 1 else "x")
    qs = negative_queries(MOCK_COMPANY, 2)
    print("platform:", platform.value, "actor:", ACTORS[platform], "queries:", qs)
    items = [i for inp in INPUTS[platform](MOCK_COMPANY, qs, 5) for i in run_actor(platform, inp)]
    print(f"{len(items)} raw items; first one:")
    print(json.dumps(items[0] if items else None, ensure_ascii=False, indent=2)[:3000])
    print("\nmapped:")
    for it in items:
        m = to_mention(it, platform, "mock-company-1", int(time.time() * 1000))
        print("-", m and (m.author, m.handle, m.reach, m.url, m.text[:80]))
