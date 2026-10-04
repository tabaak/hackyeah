-- Bluesky is a source (free search API, the live part of the feed).
alter table public.mentions drop constraint if exists mentions_platform_check;
alter table public.mentions
  add constraint mentions_platform_check
  check (platform in ('x', 'facebook', 'reddit', 'telegram', 'tiktok', 'linkedin', 'bluesky', 'news'));
