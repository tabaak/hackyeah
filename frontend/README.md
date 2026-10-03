# Palladion frontend

React + Vite + TypeScript + Tailwind v4. Mock data and mock Google login for now (`src/lib/mock.ts`, `src/lib/store.tsx`).

```bash
npm install
npm run dev   # http://localhost:5173
```

Flow: `/login` → `/onboarding` (company → optional documents) → `/app/{analytics,feed,companies}`.
Design tokens follow `../TEST_DESIGN.md`; dark theme is the default, toggle in the sidebar.
To reset the demo, sign out (clears the mock session).
