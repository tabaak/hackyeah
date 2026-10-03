-- The browser only reads/writes data through the FastAPI backend (service role), never PostgREST.
-- Direct writes with a user JWT would skip every API check (input validation, reclassification rules,
-- mention text/verdict integrity), so the API roles keep RLS-filtered reads only.
revoke insert, update, delete, truncate on all tables in schema public from anon, authenticated;
alter default privileges in schema public revoke insert, update, delete, truncate on tables from anon, authenticated;

drop policy if exists "org members manage companies" on public.companies;
create policy "org members read companies" on public.companies
  for select to authenticated using (organization_id = private.current_org());
drop policy if exists "org members update mention status" on public.mentions;
drop policy if exists "users update own name" on public.profiles;
drop policy if exists "users mark own notifications read" on public.notifications;
