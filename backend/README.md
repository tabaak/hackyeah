# Palladion API

FastAPI backend for Palladion. Routes and payloads: [`../Endpoints.md`](../Endpoints.md). Database schema: [`../supabase/migrations`](../supabase/migrations).

## Run

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp .env.example .env   # fill in SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs for the interactive API. Every `/api/v1` route needs `Authorization: Bearer <Supabase access token>` from a Google sign-in.

## How it fits together

- **Auth.** The browser signs in with Google through Supabase Auth. The API verifies the Supabase JWT (`app/deps.py`), accepts Google tokens only, and reads `user_role` and `organization_id` from claims added by the `custom_access_token_hook`.
- **Database.** The API uses the service-role key (`app/db.py`), which bypasses RLS, so every query filters by the caller's `organization_id`.
- **Documents.** Uploads go to the private `documents` bucket. A background task extracts text (PDF/TXT), chunks it, optionally embeds it, and stores `document_chunks`. `restricted` chunks are never used as evidence.
- **Mentions.** New companies get 10 demo mentions (`DEMO_SEED`). Real news comes from Serper (`SERPER_API_KEY`), analysed for prompt injection, severity and verdict. High-severity mentions notify everyone in the organization.
- **Counter-posts.** `GET /mentions/{id}/response` retrieves evidence, drafts a reply and runs the disclosure check. Drafts using `confidential` documents need compliance approval; editing a draft invalidates earlier approvals (database trigger).

## Optional services

All have fallbacks, so the API works with only the Supabase settings.

| Setting | Used for | Without it |
|---|---|---|
| `LLM_BASE_URL`, `LLM_MODEL` | Drafts and mention analysis (OpenAI-compatible) | Template drafts, keyword heuristics |
| `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL` | Vector search (must be 1536 dims) | Keyword retrieval |
| `SERPER_API_KEY` | Google News ingestion | Only demo mentions |
| `DEMO_LIVE_INTERVAL_SECONDS` | One new demo mention every N seconds | No live trickle |

## Tests

```bash
.venv/bin/python -m pytest -q
```

`tests/test_integration.py` runs the full flow against your Supabase project when `.env` has `SUPABASE_SERVICE_ROLE_KEY` and `INTEGRATION_USER_EMAIL` (a user who has signed in once). It creates a company in that user's organization and deletes it at the end.
