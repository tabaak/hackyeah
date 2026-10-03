-- Threads is no longer a source: remove its mentions and disallow the platform.
delete from public.mentions where platform = 'threads';
alter table public.mentions drop constraint if exists mentions_platform_check;
alter table public.mentions
  add constraint mentions_platform_check
  check (platform in ('x', 'facebook', 'reddit', 'telegram', 'tiktok', 'linkedin', 'news'));
