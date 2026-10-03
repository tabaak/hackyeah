-- Minimal stand-in for what a Supabase project provides before user migrations run: the API roles,
-- the auth schema (users table, uid()), the storage buckets table, the extensions schema and Supabase's
-- default grants. Only what supabase/migrations/*.sql relies on; not a full Supabase emulation.

create role anon nologin noinherit;
create role authenticated nologin noinherit;
create role service_role nologin noinherit bypassrls;
create role supabase_auth_admin nologin noinherit;

create schema extensions;
grant usage on schema extensions to anon, authenticated, service_role;

-- auth: owned by the GoTrue role, which inserts new users (and so fires the sign-up trigger).
create schema auth authorization supabase_auth_admin;
create table auth.users (
  id                  uuid primary key default gen_random_uuid(),
  email               text,
  raw_app_meta_data   jsonb not null default '{}',
  raw_user_meta_data  jsonb not null default '{}',
  created_at          timestamptz not null default now()
);
alter table auth.users owner to supabase_auth_admin;

-- Same definition as Supabase: the user id comes from the request JWT that PostgREST puts in settings.
create function auth.uid() returns uuid language sql stable as $$
  select coalesce(
    nullif(current_setting('request.jwt.claim.sub', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
  )::uuid
$$;
grant usage on schema auth to anon, authenticated, service_role;

create schema storage;
create table storage.buckets (
  id                  text primary key,
  name                text not null,
  public              boolean default false,
  file_size_limit     bigint,
  allowed_mime_types  text[],
  created_at          timestamptz default now()
);

-- Supabase grants the API roles everything in `public` by default; RLS is what restricts them.
grant usage on schema public to anon, authenticated, service_role;
alter default privileges in schema public grant all on tables to anon, authenticated, service_role;
alter default privileges in schema public grant all on functions to anon, authenticated, service_role;
alter default privileges in schema public grant all on sequences to anon, authenticated, service_role;
