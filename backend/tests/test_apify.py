import httpx

from app.schemas.common import Platform
from app.sources import apify
from app.sources.serper import MOCK_COMPANY

NOW = 1_800_000_000_000
TWEET = {"id": "1", "text": "Pekao scam!", "url": "https://x.com/a/status/1", "createdAt": "Fri Oct 02 10:00:00 +0000 2026",
         "likeCount": 5, "retweetCount": 2, "replyCount": 1, "author": {"userName": "alice", "name": "Alice"}}


def test_maps_tweet_fields():
    m = apify.to_mention(TWEET, Platform.x, "c1", NOW)
    assert (m.platform, m.handle, m.author, m.reach, m.url) == (Platform.x, "alice", "Alice", 8, TWEET["url"])
    assert m.at == 1_790_935_200_000
    assert apify.to_mention({"id": "2"}, Platform.x, "c1", NOW) is None  # no text -> skipped


def test_search_skips_failing_platform_and_dedupes():
    def handler(req: httpx.Request) -> httpx.Response:
        if "x-tweet-scraper" in req.url.path:
            return httpx.Response(200, json=[TWEET, TWEET])
        return httpx.Response(402, text="not enough credits")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        found = apify.search_posts(MOCK_COMPANY, "c1", ["Bank Pekao"], client=client)
    assert [m.platform for m in found] == [Platform.x]


# Shapes recorded from real runs of the actors now in use (trimmed)
XQUIK_TWEET = {"id": "2106456055647732092", "type": "tweet", "text": "JUST IN: = Goldman Sachs shifts forecast for next Fed rate hike to December.",
               "url": "https://x.com/michelleKir10/status/2106456055647732092", "createdAt": "Sat Oct 03 18:47:14 +0000 2026",
               "likeCount": 0, "retweetCount": 1, "replyCount": 2, "quoteCount": 0, "viewCount": 40,
               "author": {"userName": "michelleKir10", "name": "michelle Kirby"}}


def test_actors_and_inputs():
    assert apify.ACTORS[Platform.x] == "xquik/x-tweet-scraper"
    assert apify.x_input(MOCK_COMPANY, ["Bank Pekao", "Pekao"], 20) == [{"searchTerms": ["Bank Pekao", "Pekao"], "maxItems": 20, "queryType": "Latest"}]


def test_maps_xquik_tweet():
    m = apify.to_mention(XQUIK_TWEET, Platform.x, "c1", NOW)
    assert (m.handle, m.author, m.reach, m.url) == ("michelleKir10", "michelle Kirby", 3, XQUIK_TWEET["url"])
    assert m.at == 1_791_053_234_000

