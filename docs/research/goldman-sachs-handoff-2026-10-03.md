# Goldman Sachs research and frontend handoff

Collected 2026-10-03 UTC through the repository's configured connectors. The raw export, including source URLs, timestamps, full returned social post payloads, and RSS descriptions, is in [goldman-sachs-sources-2026-10-03.json](goldman-sachs-sources-2026-10-03.json).

## Collection

| Connector | Query/window | Returned |
|---|---|---:|
| Serper Google News | `Goldman Sachs`, last month, 10 max | 10 |
| Google News RSS | `Goldman Sachs when:30d`, US English, 20 max | 20 |
| Apify X (`apidojo/tweet-scraper`) | `Goldman Sachs`, latest, 10 max | 0 (actor returned `noResults: true` in all 10 rows) |
| Apify Facebook (`apify/facebook-search-scraper`) | `Goldman Sachs`, posts, 10 max | 10 |

All requests completed. The X actor returned ten `noResults` markers (not ten posts), so its raw response is preserved separately in [goldman-sachs-apify-x-raw-2026-10-03.json](goldman-sachs-apify-x-raw-2026-10-03.json). Google News RSS overlaps heavily with Serper; deduplicate by resolving feed links to canonical article URLs. The RSS output uses Google redirect URLs and HTML descriptions, and Serper snippets are excerpts, not full article bodies. All 10 Serper results are on-topic, but mostly routine business/market coverage rather than reputation incidents. In the 10 Facebook results, about 8 are Goldman-related; 2 are clearly noise, while several related posts use sensational claims that need independent verification. Relevance is not factual accuracy. The source adapters currently assign neutral placeholder classifications (`low` / `insufficient_evidence`); this export is source data, not a verified risk assessment. No Threads actor was run.

## What exists in the code

- `backend/app/sources/apify.py` has X, Facebook, and Threads actor adapters. `search_posts()` defaults to X and Facebook, filters age, and maps results into the shared `Mention` schema. The active API does not call this adapter yet.
- `backend/app/services/news.py` and `backend/app/sources/serper.py` use Serper's Google News search endpoint. This is configured as the active `news` sync; it is not an RSS parser.
- There is no RSS adapter/module in the current code. The Google News RSS feed was fetched directly for this saved research sample. The project plan mentions RSS, but implementation remains a follow-up task.
- `POST /feed/sources/{platform}/sync` currently supports only `news`; other sources return 501. Source status behaves similarly.
- The active news sync runs `services/ingest.py` and the classifier before saving mentions. Apify needs to be routed through that same ingestion/classification path before its results appear in the authenticated feed.

## Frontend/backend connection map

The frontend's `frontend/src/lib/api.ts` already wraps requests, uses `VITE_API_URL` (default `http://localhost:8000/api/v1`), and attaches the Supabase access token. Auth calls `/me`. The current `frontend/src/lib/store.tsx` still loads tracked companies from localStorage, seeds mock posts, and simulates a new post every 15 seconds. The central migration point is replacing those store paths with API-backed state and removing seeded/simulated feed items after initial migration.

| Frontend operation | Backend contract |
|---|---|
| Load/create/update companies | `GET /companies`, `POST /companies`, `PUT /companies/{id}`; use returned server IDs as canonical IDs |
| Load/filter live feed | `GET /mentions?company_id=…&platform=…&severity=…&status=…&limit=…`; response shape is camelCase and timestamps are Unix milliseconds |
| Live updates | `GET /mentions/stream?company_id=…` (SSE), or poll `since_timestamp` / `since_id` |
| Change triage status | `PATCH /mentions/{id}/status` with `{ "status": "…" }` |
| Upload company files | `GET/POST /companies/{id}/documents`; multipart fields are `files` and matching `classifications` |
| Sync sources | `POST /feed/sources/news/sync` today; add and expose `x`, `facebook`, and `rss` only after adapters are routed through ingest |

One link-related contract gap to fix during wiring: the database stores the mention URL and the API schema has a URL field, but `backend/app/services/mappers.py` currently omits `url` when mapping database rows. Add that field so the feed can link to source content instead of synthesizing author/profile links.

## Suggested next implementation sequence

1. Add an RSS adapter that maps feed entries into the same source-neutral item shape; keep Google News RSS configuration separate from the current Serper search connector.
2. Route Apify X/Facebook and RSS through the shared ingestion and classification pipeline; add bounded sync/status endpoints with organization scoping, dedupe, and per-source errors.
3. Add `url` to the database-to-API mention mapper and confirm the frontend `Post` type retains source URLs.
4. Replace localStorage company/feed writes and generated seed posts with API calls, then load the feed and status changes from the backend; enable SSE or polling for updates.
5. Review the saved 40-item collection against the classifier and verify both true relevance and false-positive behavior before using it as the Goldman Sachs demo dataset.


## Initial quality assessment

For a Goldman Sachs reputation-monitoring demo, this is a useful connector smoke test, but not yet a clean demo corpus. Google News gives the strongest signal and broad company coverage; RSS substantially repeats it. Facebook has weak precision and requires exact entity/relevance checks plus claim verification. X yielded no posts in this run. There are no labeled examples in this export, so classifier precision/recall cannot yet be measured. Before using items in a demo, deduplicate news, strip RSS HTML and resolve canonical URLs, exclude irrelevant social hits, and hand-label a small set for risk relevance and factual support.
