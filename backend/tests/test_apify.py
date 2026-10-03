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
THREADS_POST = {"record_type": "post", "post_url": "https://www.threads.com/@printisyurik/post/DeCvAObE1k2", "post_code": "DeCvAObE1k2",
                "text_content": "My husband and I are both analysts at Goldman Sachs.", "created_at": "2026-10-03T18:45:43+00:00",
                "like_count": 4, "reply_count": 3, "repost_count": 1, "quote_count": 0, "username": "printisyurik", "display_name": "Yurik"}


def test_actors_and_inputs():
    assert apify.ACTORS[Platform.x] == "xquik/x-tweet-scraper" and apify.ACTORS[Platform.threads] == "futurizerush/meta-threads-scraper"
    assert apify.x_input(MOCK_COMPANY, ["Bank Pekao", "Pekao"], 20) == [{"searchTerms": ["Bank Pekao", "Pekao"], "maxItems": 20, "queryType": "Latest"}]
    # Threads: a single run and a single keyword, with the actor's minimum of 10 posts
    assert apify.threads_input(MOCK_COMPANY, ["Bank Pekao", "Pekao"], 5) == [
        {"mode": "search", "keywords": ["Bank Pekao"], "max_posts": 10, "search_filter": "recent"}]
    assert apify.threads_input(MOCK_COMPANY, ["Bank Pekao"], 25)[0]["max_posts"] == 25


def test_maps_xquik_tweet():
    m = apify.to_mention(XQUIK_TWEET, Platform.x, "c1", NOW)
    assert (m.handle, m.author, m.reach, m.url) == ("michelleKir10", "michelle Kirby", 40, XQUIK_TWEET["url"])  # reach = views
    assert m.at == 1_791_053_234_000


def test_maps_threads_post():
    m = apify.to_mention(THREADS_POST, Platform.threads, "c1", NOW)
    assert (m.handle, m.author, m.reach, m.url) == ("printisyurik", "Yurik", 8, THREADS_POST["post_url"])
    assert m.text.startswith("My husband") and m.at == 1_791_053_143_000


def test_threads_profile_rows_are_skipped():
    assert apify.to_mention({"record_type": "profile", "username": "x", "bio": "Goldman Sachs fan"}, Platform.threads, "c1", NOW) is None
