# Palladion frontend

React + Vite + TypeScript + Tailwind v4. Google sign-in uses Supabase Auth. Company profiles are created through the FastAPI backend and stored in Supabase, scoped to the account's organization.

```bash
npm install
npm run dev   # http://localhost:5173
```

Copy `.env.example` to `.env.local` and configure the Supabase URL, publishable key and API URL. The backend needs its Supabase service-role key and the initial database migration; see `../backend/README.md`.

Flow: `/login` → `/onboarding` (company → optional documents) → `/app/{analytics,feed,companies}`.
On sign-in, the app loads `/me` and `/companies` before choosing onboarding or the dashboard. Existing companies are restored on reload and repeat sign-in. A failed request offers retry instead of treating the account as empty.

Mentions, the live feed, analytics and counter-posts remain mock data. Document selection remains a demo; its metadata is stored separately per account in the browser and does not upload files to the API. Company IDs and timestamps come from Supabase.
Design tokens follow `../TEST_DESIGN.md`; dark theme is the default, toggle in the sidebar.
Sign-out clears the current workspace from memory; it does not delete saved company profiles.
