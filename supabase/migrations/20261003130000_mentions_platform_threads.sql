-- Allow `threads` in mentions.platform on databases created before it was added to the init migration.
-- Safe to run more than once, and on a fresh database (where the constraint already allows it).
alter table public.mentions drop constraint if exists mentions_platform_check;
alter table public.mentions
  add constraint mentions_platform_check
  check (platform in ('x', 'facebook', 'reddit', 'telegram', 'tiktok', 'linkedin', 'threads', 'news'));
