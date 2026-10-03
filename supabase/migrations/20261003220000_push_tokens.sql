-- Expo push tokens of the mobile app, one row per device. A device that signs in to another
-- account moves with it (primary key = token). Written and read only by the API (service role).
create table public.push_tokens (
  token            text primary key,
  user_id          uuid not null references auth.users (id) on delete cascade,
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  platform         text not null check (platform in ('ios', 'android')),
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
create index on public.push_tokens (user_id);

-- RLS on with no policies: invisible to anon/authenticated, so tokens never leave the API
alter table public.push_tokens enable row level security;
