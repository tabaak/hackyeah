# Palladion

## AI Control Layer — judge quick start

Run `make control-demo` for five explicitly **fictional**, reproducible cases with no API keys, model weights, Supabase or frontend. Run `make control-test` for the isolated gateway/privacy/policy test suite. Both commands use [uv](https://docs.astral.sh/uv/) and a separate locked Python environment.

The local module provides Jev/OpenJev filtering, a Qwen3.8-27B adapter, private document processing, evidence-linked company risk assessments, policy review and sector summaries. High risk triggers compliance review and permitted remediation, not automatic client rejection. Fixture success is separate from live model readiness.

See the [control-layer guide](backend/app/control_layer/README.md) for architecture, live setup, API examples and privacy boundaries, and [validation results](backend/app/control_layer/VALIDATION.md) for what was actually tested. The control API runs separately on `127.0.0.1:8002`; the existing application below retains its original storage and model behavior.

## Run the app with Docker

Requirements: Docker Desktop with Compose v2, Make, and credentials for the configured Supabase project.

1. Create the local environment files if needed:

   ```sh
   make setup
   ```

2. In `.env`, set `SUPABASE_URL`. In `frontend/.env.local`, set `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`, and `VITE_API_URL=http://localhost:8000/api/v1`. Get these from the Supabase project API settings. Add `SUPABASE_SERVICE_ROLE_KEY` to `.env` to enable database-backed API routes; without it, the UI/demo can start but those routes return 503. Keep the service-role key server-side; never put it in a `VITE_` variable. `SUPABASE_JWT_SECRET` is needed for projects that still sign tokens with legacy HS256 keys.

3. Build and start the API and frontend:

   ```sh
   make up
   ```

   Open <http://localhost:5173>. The API is at <http://localhost:8000>, with interactive docs at <http://localhost:8000/docs>.

The app uses Supabase for Google sign-in, database, and file storage. The Google provider and database migration must already be configured in that Supabase project. The API falls back to deterministic analysis and template drafts when `LLM_BASE_URL` is empty. The optional local Bonsai server runs on the host; to use it from Docker, set `LLM_BASE_URL=http://host.docker.internal:<port>/v1`.

Useful commands:

```sh
make logs       # follow API and frontend logs
make ps         # container status
make down       # stop containers; preserve the frontend dependency volume
make test       # backend tests
```

The Compose setup is for local development: frontend and backend source folders are mounted for live reload. It does not start a separate database because this backend relies on Supabase Auth, Storage, and its custom JWT hook as well as Postgres.
