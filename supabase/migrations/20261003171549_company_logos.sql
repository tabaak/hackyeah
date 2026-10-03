-- Private logos: the API checks organization ownership before writing or signing URLs.
-- Direct browser writes/reads have no storage.objects policy for this bucket.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('company-logos', 'company-logos', false, 2097152, array['image/webp'])
on conflict (id) do nothing;
