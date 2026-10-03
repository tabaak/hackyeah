-- Palladion initial schema. Matches Endpoints.md and backend/app/schemas.
-- Conventions (defence-reputation-mvp-plan.md §10): UUID ids, timestamptz UTC, statuses as text + CHECK.
-- The API converts timestamptz <-> Unix ms (`at`, `createdAt`) at the edge.

create extension if not exists vector with schema extensions;

create schema if not exists private;

-- ---------------------------------------------------------------------------
-- Tenancy: organizations and user profiles
-- ---------------------------------------------------------------------------

create table public.organizations (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  created_at  timestamptz not null default now()
);

create table public.profiles (
  user_id          uuid primary key references auth.users (id) on delete cascade,
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  name             text not null default '',
  email            text not null,
  role             text not null default 'analyst' check (role in ('analyst', 'compliance')),
  created_at       timestamptz not null default now()
);
create index on public.profiles (organization_id);

-- Organization of the calling user; used by every RLS policy.
create function private.current_org() returns uuid
language sql stable security definer set search_path = '' as $$
  select organization_id from public.profiles where user_id = auth.uid()
$$;

create function private.user_role() returns text
language sql stable security definer set search_path = '' as $$
  select role from public.profiles where user_id = auth.uid()
$$;

-- New sign-up -> own organization + analyst profile. Invite flows can move the profile later.
-- Google is the only allowed sign-in method: any other provider aborts the sign-up.
create function private.handle_new_user() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  org_id uuid;
begin
  if new.raw_app_meta_data ->> 'provider' is distinct from 'google' then
    raise exception 'Only Google sign-in is allowed';
  end if;

  insert into public.organizations (name)
  values (coalesce(new.raw_user_meta_data ->> 'organization', split_part(new.email, '@', 2)))
  returning id into org_id;

  insert into public.profiles (user_id, organization_id, name, email)
  values (new.id, org_id, coalesce(new.raw_user_meta_data ->> 'full_name', ''), new.email);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function private.handle_new_user();

-- Custom access token hook (enabled in supabase/config.toml / Dashboard -> Auth -> Hooks):
-- adds `user_role` and `organization_id` claims so the API authorizes from the JWT alone.
create function public.custom_access_token_hook(event jsonb) returns jsonb
language plpgsql stable set search_path = '' as $$
declare
  claims  jsonb := event -> 'claims';
  p_role  text;
  p_org   uuid;
begin
  select role, organization_id into p_role, p_org
    from public.profiles where user_id = (event ->> 'user_id')::uuid;

  if p_role is not null then
    claims := jsonb_set(claims, '{user_role}', to_jsonb(p_role));
    claims := jsonb_set(claims, '{organization_id}', to_jsonb(p_org));
  end if;
  return jsonb_set(event, '{claims}', claims);
end;
$$;

grant usage on schema public to supabase_auth_admin;
grant execute on function public.custom_access_token_hook to supabase_auth_admin;
revoke execute on function public.custom_access_token_hook from public, anon, authenticated;
grant select on table public.profiles to supabase_auth_admin;

-- ---------------------------------------------------------------------------
-- Tracked companies
-- ---------------------------------------------------------------------------

create table public.companies (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  name             text not null,
  website          text not null default '',
  aliases          text[] not null default '{}',
  sector           text not null check (sector in ('Banking', 'Defence', 'Fintech', 'Energy', 'Other')),
  country          text not null,
  people           text[] not null default '{}',
  topics           text[] not null default '{}',
  created_at       timestamptz not null default now()
);
create index on public.companies (organization_id);

-- Child rows copy organization_id from their company so RLS stays a simple column check.
create function private.set_org_from_company() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  select organization_id into new.organization_id from public.companies where id = new.company_id;
  if new.organization_id is null then
    raise exception 'company % not found', new.company_id;
  end if;
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- Documents (knowledge base) and vector chunks
-- ---------------------------------------------------------------------------

create table public.documents (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  company_id       uuid not null references public.companies (id) on delete cascade,
  name             text not null,
  size             bigint not null check (size >= 0),
  storage_path     text not null unique,  -- documents bucket: {organization_id}/{document_id}/{name}
  classification   text not null check (classification in ('public', 'internal', 'confidential', 'restricted')),
  status           text not null default 'processing' check (status in ('processing', 'ready', 'failed')),
  error            text,
  uploaded_by      uuid references auth.users (id) on delete set null,
  created_at       timestamptz not null default now()
);
create index on public.documents (company_id);

create trigger documents_set_org before insert on public.documents
  for each row execute function private.set_org_from_company();

-- Embedding dimension must match the chosen embedding model (1536 = OpenAI text-embedding-3-small).
-- No ANN index: brute force is fine at MVP volume (plan §10).
create table public.document_chunks (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  document_id      uuid not null references public.documents (id) on delete cascade,
  chunk_index      int not null,
  content          text not null,
  classification   text not null check (classification in ('public', 'internal', 'confidential', 'restricted')),
  embedding        extensions.vector(1536),
  fingerprints     jsonb not null default '{}',  -- for the disclosure check
  unique (document_id, chunk_index)
);

-- Reclassifying a document reclassifies its chunks.
create function private.sync_chunk_classification() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  update public.document_chunks set classification = new.classification where document_id = new.id;
  return new;
end;
$$;

create trigger documents_sync_classification
  after update of classification on public.documents
  for each row execute function private.sync_chunk_classification();

-- ---------------------------------------------------------------------------
-- Mentions and clusters
-- ---------------------------------------------------------------------------

create table public.clusters (
  id                uuid primary key default gen_random_uuid(),
  organization_id   uuid not null references public.organizations (id) on delete cascade,
  company_id        uuid not null references public.companies (id) on delete cascade,
  size              int not null default 0,        -- API: cluster.size
  unique_authors    int not null default 0,        -- API: cluster.accounts
  first_seen_at     timestamptz not null default now(),
  last_seen_at      timestamptz not null default now(),
  burst_score       real,
  signals           jsonb not null default '{}'    -- new-account share, duplicates, synchrony
);
create index on public.clusters (organization_id, last_seen_at desc);

create trigger clusters_set_org before insert on public.clusters
  for each row execute function private.set_org_from_company();

create table public.mentions (
  id                   uuid primary key default gen_random_uuid(),
  organization_id      uuid not null references public.organizations (id) on delete cascade,
  company_id           uuid not null references public.companies (id) on delete cascade,
  platform             text not null check (platform in ('x', 'facebook', 'reddit', 'telegram', 'tiktok', 'linkedin', 'news')),
  external_id          text not null,
  url                  text,
  author               text not null default '',
  handle               text not null default '',
  author_created_at    timestamptz,
  lang                 text,
  text                 text not null,
  published_at         timestamptz not null,       -- API: at
  ingested_at          timestamptz not null default now(),
  reach                int not null default 0,
  severity             text not null default 'low' check (severity in ('high', 'medium', 'low')),
  verdict              text not null default 'insufficient_evidence'
                       check (verdict in ('contradicted_by_documents', 'supported_by_documents', 'insufficient_evidence', 'opinion')),
  reason               text not null default '',
  cluster_id           uuid references public.clusters (id) on delete set null,
  injection_suspected  boolean not null default false,  -- API: injection
  status               text not null default 'new' check (status in ('new', 'responded', 'dismissed')),
  embedding            extensions.vector(1536),
  unique (company_id, platform, external_id)              -- idempotent ingestion
);
create index on public.mentions (organization_id, published_at desc);
create index on public.mentions (company_id, published_at desc);
create index on public.mentions (cluster_id);

create trigger mentions_set_org before insert on public.mentions
  for each row execute function private.set_org_from_company();

-- ---------------------------------------------------------------------------
-- Counter-post response, approvals, outbox
-- ---------------------------------------------------------------------------

create table public.mention_responses (
  mention_id           uuid primary key references public.mentions (id) on delete cascade,
  organization_id      uuid not null references public.organizations (id) on delete cascade,
  draft                text not null default '',
  draft_version        int not null default 1,
  draft_hash           text not null default '',   -- sha256 of draft, set by the API
  evidence             jsonb not null default '[]', -- [{docId, name, classification}], never restricted
  needs_compliance     boolean not null default false,
  disclosure_reason    text not null default '',
  disclosure_findings  jsonb not null default '[]',
  injection_blocked    boolean not null default false,
  updated_at           timestamptz not null default now()
);

create function private.set_org_from_mention() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  select organization_id into new.organization_id from public.mentions where id = new.mention_id;
  if new.organization_id is null then
    raise exception 'mention % not found', new.mention_id;
  end if;
  return new;
end;
$$;

create trigger mention_responses_set_org before insert on public.mention_responses
  for each row execute function private.set_org_from_mention();

create table public.approvals (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  mention_id       uuid not null references public.mentions (id) on delete cascade,
  payload_hash     text not null,
  draft_version    int not null,
  required_role    text not null check (required_role in ('analyst', 'compliance')),
  status           text not null default 'pending' check (status in ('pending', 'approved', 'rejected', 'invalidated')),
  requested_by     uuid references auth.users (id) on delete set null,
  decided_by       uuid references auth.users (id) on delete set null,
  decided_at       timestamptz,
  comment          text,
  created_at       timestamptz not null default now()
);
create index on public.approvals (mention_id, created_at desc);

create trigger approvals_set_org before insert on public.approvals
  for each row execute function private.set_org_from_mention();

-- A new draft version invalidates every pending/approved approval in the same transaction (plan §10).
create function private.invalidate_approvals() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.draft_hash is distinct from old.draft_hash then
    update public.approvals
       set status = 'invalidated'
     where mention_id = new.mention_id and status in ('pending', 'approved');
    new.draft_version := old.draft_version + 1;
  end if;
  new.updated_at := now();
  return new;
end;
$$;

create trigger mention_responses_invalidate
  before update on public.mention_responses
  for each row execute function private.invalidate_approvals();

-- Simulated publication channel (planned: POST /mentions/{id}/response/publish).
create table public.outbox (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  mention_id       uuid not null references public.mentions (id) on delete cascade,
  approval_id      uuid not null references public.approvals (id),
  channel          text not null,
  text             text not null,
  published_at     timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Notifications (per user, so read state is per user)
-- ---------------------------------------------------------------------------

create table public.notifications (
  id               uuid primary key default gen_random_uuid(),
  organization_id  uuid not null references public.organizations (id) on delete cascade,
  user_id          uuid not null references auth.users (id) on delete cascade,
  mention_id       uuid references public.mentions (id) on delete cascade,
  kind             text not null check (kind in ('critical_mention', 'approval_requested', 'approval_decided')),
  title            text not null,
  severity         text not null check (severity in ('high', 'medium', 'low')),
  created_at       timestamptz not null default now(),  -- API: at
  read_at          timestamptz                          -- API: read = read_at is not null
);
create index on public.notifications (user_id, created_at desc);

-- ---------------------------------------------------------------------------
-- Background jobs (service role only)
-- ---------------------------------------------------------------------------

create table private.jobs (
  id            uuid primary key default gen_random_uuid(),
  kind          text not null,  -- index_document | sync_source | analyze_mention | generate_response
  payload       jsonb not null default '{}',
  status        text not null default 'queued' check (status in ('queued', 'running', 'done', 'failed')),
  attempts      int not null default 0,
  available_at  timestamptz not null default now(),
  last_error    text,
  created_at    timestamptz not null default now()
);
create index on private.jobs (status, available_at);

-- ---------------------------------------------------------------------------
-- Row level security. The FastAPI backend uses the service role (bypasses RLS);
-- these policies protect direct access with a user JWT.
-- ---------------------------------------------------------------------------

alter table public.organizations     enable row level security;
alter table public.profiles          enable row level security;
alter table public.companies         enable row level security;
alter table public.documents         enable row level security;
alter table public.document_chunks   enable row level security;  -- no policies: service role only
alter table public.clusters          enable row level security;
alter table public.mentions          enable row level security;
alter table public.mention_responses enable row level security;
alter table public.approvals         enable row level security;
alter table public.outbox            enable row level security;
alter table public.notifications     enable row level security;

create policy "members read own organization" on public.organizations
  for select to authenticated using (id = private.current_org());

create policy "members read profiles in organization" on public.profiles
  for select to authenticated using (organization_id = private.current_org());
create policy "auth admin reads profiles for token hook" on public.profiles
  for select to supabase_auth_admin using (true);
create policy "users update own name" on public.profiles
  for update to authenticated using (user_id = auth.uid())
  with check (user_id = auth.uid() and role = private.user_role() and organization_id = private.current_org());

create policy "org members manage companies" on public.companies
  for all to authenticated
  using (organization_id = private.current_org())
  with check (organization_id = private.current_org());

-- Restricted documents are visible to compliance only.
create policy "org members read documents" on public.documents
  for select to authenticated
  using (organization_id = private.current_org()
         and (classification <> 'restricted' or private.user_role() = 'compliance'));

create policy "org members read clusters" on public.clusters
  for select to authenticated using (organization_id = private.current_org());

create policy "org members read mentions" on public.mentions
  for select to authenticated using (organization_id = private.current_org());
create policy "org members update mention status" on public.mentions
  for update to authenticated
  using (organization_id = private.current_org())
  with check (organization_id = private.current_org());

create policy "org members read responses" on public.mention_responses
  for select to authenticated using (organization_id = private.current_org());

create policy "org members read approvals" on public.approvals
  for select to authenticated using (organization_id = private.current_org());

create policy "org members read outbox" on public.outbox
  for select to authenticated using (organization_id = private.current_org());

create policy "users read own notifications" on public.notifications
  for select to authenticated using (user_id = auth.uid());
create policy "users mark own notifications read" on public.notifications
  for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

-- ---------------------------------------------------------------------------
-- Storage: private bucket; files are served only through signed URLs from the API.
-- ---------------------------------------------------------------------------

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('documents', 'documents', false, 20971520, array['application/pdf', 'text/plain'])
on conflict (id) do nothing;

-- ---------------------------------------------------------------------------
-- Vector search for the response generator (service role; caller filters by classification).
-- ---------------------------------------------------------------------------

create function public.match_document_chunks(
  p_company_id       uuid,
  p_query_embedding  extensions.vector(1536),
  p_match_count      int default 8,
  p_max_classification text default 'confidential'  -- restricted is never returned
) returns table (chunk_id uuid, document_id uuid, document_name text, classification text, content text, similarity float)
language sql stable set search_path = '' as $$
  select c.id, d.id, d.name, c.classification, c.content,
         1 - (c.embedding operator(extensions.<=>) p_query_embedding)
    from public.document_chunks c
    join public.documents d on d.id = c.document_id
   where d.company_id = p_company_id
     and d.status = 'ready'
     and c.embedding is not null
     and c.classification <> 'restricted'
     and array_position(array['public', 'internal', 'confidential'], c.classification)
         <= array_position(array['public', 'internal', 'confidential'], p_max_classification)
   order by c.embedding operator(extensions.<=>) p_query_embedding
   limit p_match_count
$$;

revoke execute on function public.match_document_chunks from public, anon, authenticated;
