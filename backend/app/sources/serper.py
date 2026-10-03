"""Google News search through Serper -> `Mention` objects (platform = news).

Serper returns only title/link/snippet/source/date. Severity, verdict, reason and reach come from later
analysis, so they are filled with neutral placeholders here.

Try it with a mock company (costs a few Serper credits):
    python -m app.sources.serper
"""
import hashlib
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.schemas.common import MentionStatus, Platform, Severity, Verdict
from app.schemas.companies import CompanyDraft
from app.schemas.feed import Mention

SERPER_NEWS_URL = "https://google.serper.dev/news"
SERPER_SEARCH_URL = "https://google.serper.dev/search"

# Frontend country names -> Google `gl` code (None = no geo bias)
COUNTRY_GL = {
    "Poland": "pl", "Germany": "de", "Ukraine": "ua", "Lithuania": "lt", "Czechia": "cz",
    "United Kingdom": "gb", "United States": "us", "Global": None,
}
PERIOD_TBS = {"h": "qdr:h", "d": "qdr:d", "w": "qdr:w", "m": "qdr:m", "3m": "qdr:m3", "y": "qdr:y"}
_UNIT_SECONDS = {
    "second": 1, "sec": 1, "minute": 60, "min": 60, "hour": 3600, "hr": 3600,
    "day": 86400, "week": 7 * 86400, "month": 30 * 86400, "year": 365 * 86400,
}
# Longest unit first so "minutes" is read as minute+s, not min+utes.
_RELATIVE_DATE = re.compile(r"(\d+)\s+(" + "|".join(sorted(_UNIT_SECONDS, key=len, reverse=True)) + r")s?\s+ago")


class SerperError(RuntimeError):
    pass


def build_queries(company: CompanyDraft, max_queries: int = 4) -> list[str]:
    """Plain-text queries, one credit each: the name, the first alias, then the name plus a risk topic.

    Measured on Serper /news: a quoted phrase and an `OR` query both returned 0 results, the plain name returned 10,
    and name+topic queries are narrow (0-1 results) but target the threats we care about.
    """
    name = company.name.strip()
    alias = next((a.strip() for a in company.aliases if a.strip() and a.strip().lower() != name.lower()), None)
    queries = [name, *([alias] if alias else []), *(f"{name} {t}" for t in company.topics)]
    return list(dict.fromkeys(queries))[:max_queries]


def parse_date(text: str | None, now_ms: int) -> int:
    """Serper dates are relative ("4 days ago") or occasionally absolute. Resolution is coarse; fall back to now."""
    s = (text or "").strip().lower()
    m = _RELATIVE_DATE.match(s)
    if m:
        return now_ms - int(m[1]) * _UNIT_SECONDS[m[2]] * 1000
    if s == "yesterday":
        return now_ms - 86400 * 1000
    for fmt in ("%b %d, %Y", "%d %b %Y", "%Y-%m-%d"):
        try:
            return int(datetime.strptime(text.strip(), fmt).replace(tzinfo=timezone.utc).timestamp() * 1000)
        except (ValueError, AttributeError):
            pass
    return now_ms


def to_mention(article: dict, company_id: str, now_ms: int, platform: Platform = Platform.news) -> Mention:
    link = article["link"]
    host = urlparse(link).netloc.removeprefix("www.")
    title, snippet = article.get("title", "").strip(), article.get("snippet", "").strip()
    return Mention(
        id=f"{platform.value}_" + hashlib.sha1(f"{company_id}|{link}".encode()).hexdigest()[:12],
        company_id=company_id,
        platform=platform,
        author=article.get("source") or host,
        handle=host,
        text=f"{title}. {snippet}" if snippet else title,
        at=parse_date(article.get("date"), now_ms),
        severity=Severity.low,  # placeholders until analysis fills them in
        verdict=Verdict.insufficient_evidence,
        reason="",
        reach=0,
        cluster=None,
        injection=False,
        status=MentionStatus.new,
        url=link,
    )


def search_news(
    company: CompanyDraft,
    company_id: str,
    *,
    period: str = "w",
    per_query: int = 10,
    max_queries: int = 4,
    queries: list[str] | None = None,
    client: httpx.Client | None = None,
) -> list[Mention]:
    """Search Google News for the company; returns de-duplicated mentions, newest first."""
    return _search(SERPER_NEWS_URL, "news", company, company_id, queries or build_queries(company, max_queries),
                   period, per_query, client)


def search_web(
    company: CompanyDraft,
    company_id: str,
    queries: list[str],
    *,
    period: str = "3m",
    per_query: int = 10,
    client: httpx.Client | None = None,
) -> list[Mention]:
    """Plain Google results (forums, review sites, Reddit): complaints that never reach the news.

    Reddit links become platform=reddit, everything else platform=news (`url` holds the link either way).
    Organic results often carry no date; those get "now" as a fallback.
    """
    return _search(SERPER_SEARCH_URL, "organic", company, company_id, queries, period, per_query, client)


def _search(endpoint, key, company, company_id, queries, period, per_query, client) -> list[Mention]:
    if not settings.serper_api_key and client is None:
        raise SerperError("SERPER_API_KEY is not set")
    if period not in PERIOD_TBS:
        raise ValueError(f"period must be one of {sorted(PERIOD_TBS)}, got {period!r}")
    own = client is None
    client = client or httpx.Client(timeout=30)
    now_ms, seen, out = int(time.time() * 1000), set(), []
    try:
        for q in queries:
            body = {"q": q, "num": per_query, "tbs": PERIOD_TBS[period]}
            if gl := COUNTRY_GL.get(company.country):
                body["gl"] = gl
            try:
                r = client.post(endpoint, headers={"X-API-KEY": settings.serper_api_key}, json=body)
                if r.status_code != 200:
                    raise SerperError(f"Serper {r.status_code}: {r.text[:200]}")
                articles = r.json().get(key, [])
            except (httpx.HTTPError, ValueError) as e:  # network failure or a non-JSON body
                raise SerperError(f"Serper request failed: {e}") from e
            for a in articles:
                if a.get("link") and a["link"] not in seen:
                    seen.add(a["link"])
                    host = urlparse(a["link"]).netloc
                    is_reddit = key == "organic" and (host == "reddit.com" or host.endswith(".reddit.com"))
                    out.append(to_mention(a, company_id, now_ms, Platform.reddit if is_reddit else Platform.news))
    finally:
        if own:
            client.close()
    return sorted(out, key=lambda m: m.at, reverse=True)


# Mock of what the frontend sends on company creation (see frontend CompanyForm / CompanyDraft).
MOCK_COMPANY = CompanyDraft(
    name="Bank Pekao", website="https://www.pekao.com.pl", aliases=["Pekao", "Pekao S.A."],
    sector="Banking", country="Poland", people=[], topics=["Frozen withdrawals", "Data breach"],
)

DEMO_COMPANY = CompanyDraft(
    name="Goldman Sachs", website="https://www.goldmansachs.com", aliases=["Goldman", "GS"],
    sector="Banking", country="United States", people=[],
    topics=["SEC investigation", "Trading losses", "Market manipulation", "Data breach", "Sanctions", "Layoffs"],
)

if __name__ == "__main__":
    print("queries:", build_queries(MOCK_COMPANY))
    found = search_news(MOCK_COMPANY, "mock-company-1")
    print(f"{len(found)} mentions")
    for m in found[:8]:
        print(f"- [{m.platform.value}] {m.author} ({m.handle}) at={m.at} :: {m.text[:90]}\n    {m.url}")
