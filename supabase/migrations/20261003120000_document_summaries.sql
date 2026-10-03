-- AI summary of each uploaded document, written by the API's background processing (app/services/documents.py).
-- NULL while processing or when processing failed. The summary carries the document's classification:
-- the RLS policy on documents already hides restricted rows from non-compliance users.
alter table public.documents
  add column summary       text,
  add column summarized_at timestamptz;
