-- Mentions: allow `threads` as a platform, and store the author avatar and attached images.
-- Idempotent: safe on a fresh database and on one created before these changes.

-- Allow `threads` in mentions.platform on databases created before it was added to the init migration.
alter table public.mentions drop constraint if exists mentions_platform_check;
alter table public.mentions
  add constraint mentions_platform_check
  check (platform in ('x', 'facebook', 'reddit', 'telegram', 'tiktok', 'linkedin', 'threads', 'news'));

-- Author avatar and attached images of a mention (links to the source's own files; nothing is copied).
alter table public.mentions add column if not exists avatar_url text;
alter table public.mentions add column if not exists media_urls jsonb not null default '[]';
