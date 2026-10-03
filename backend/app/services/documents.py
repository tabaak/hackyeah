"""Document ingestion: storage upload, text extraction, chunking, embeddings."""
import io
import logging
import re
import uuid

from pypdf import PdfReader

from app.db import DOCUMENTS_BUCKET, get_db
from app.services import llm

log = logging.getLogger(__name__)

MAX_BYTES = 5 * 1024 * 1024  # matches the frontend limit
CHUNK_CHARS = 900
CHUNK_OVERLAP = 150
CONTENT_TYPES = {".pdf": "application/pdf", ".txt": "text/plain"}


def content_type_for(name: str) -> str | None:
    m = re.search(r"\.[^.]+$", name.lower())
    return CONTENT_TYPES.get(m.group(0)) if m else None


def storage_path(org_id: str, doc_id: str, name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "file"
    return f"{org_id}/{doc_id}/{safe}"


def extract_text(name: str, data: bytes) -> str:
    if name.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    return data.decode("utf-8", errors="replace")


def chunk_text(text: str, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Paragraph-aware chunks of roughly `size` chars; long paragraphs are split with overlap."""
    text = re.sub(r"[ \t]+", " ", text.replace("\r", ""))
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for p in paragraphs:
        if len(p) > size:
            if current:
                chunks.append(current)
                current = ""
            step = size - overlap
            chunks.extend(p[i:i + size] for i in range(0, len(p), step) if p[i:i + size].strip())
            continue
        if len(current) + len(p) + 2 > size and current:
            chunks.append(current)
            current = p
        else:
            current = f"{current}\n\n{p}" if current else p
    if current:
        chunks.append(current)
    return chunks


def fingerprints(content: str, step: int = 3) -> list[str]:
    """6-word shingles every `step` words, used by the disclosure check to spot verbatim reuse.
    Comparing dense (step=1) shingles of a draft against these catches any shared run of 8+ words."""
    words = re.findall(r"\w+", content.lower())
    return sorted({" ".join(words[i:i + 6]) for i in range(0, max(0, len(words) - 5), step)})


def process_document(doc_id: str, data: bytes) -> None:
    """Background task: extract -> chunk -> embed -> store chunks; marks the document ready or failed."""
    db = get_db()
    doc = db.table("documents").select("*").eq("id", doc_id).single().execute().data
    try:
        text = extract_text(doc["name"], data)
        chunks = chunk_text(text)
        if not chunks:
            raise ValueError("No text found (scanned PDF without a text layer?)")
        vectors = llm.embed(chunks)
        rows = [
            {
                "organization_id": doc["organization_id"],
                "document_id": doc_id,
                "chunk_index": i,
                "content": c,
                "classification": doc["classification"],
                "fingerprints": {"shingles": fingerprints(c)},
                "embedding": llm.vector_literal(vectors[i]) if vectors else None,
            }
            for i, c in enumerate(chunks)
        ]
        db.table("document_chunks").delete().eq("document_id", doc_id).execute()
        for i in range(0, len(rows), 100):
            db.table("document_chunks").insert(rows[i:i + 100]).execute()
        db.table("documents").update({"status": "ready", "error": None}).eq("id", doc_id).execute()
    except Exception as e:
        log.exception("Document %s failed", doc_id)
        db.table("documents").update({"status": "failed", "error": str(e)[:500]}).eq("id", doc_id).execute()


def upload(org_id: str, company_id: str, user_id: str, name: str, data: bytes, classification: str) -> dict:
    """Stores the file first, then the row (status processing); the file is removed if the row insert fails."""
    db = get_db()
    doc_id = str(uuid.uuid4())
    path = storage_path(org_id, doc_id, name)
    db.storage.from_(DOCUMENTS_BUCKET).upload(path, data, {"content-type": content_type_for(name) or "application/octet-stream", "upsert": "true"})
    try:
        return db.table("documents").insert({
            "id": doc_id,
            "organization_id": org_id,
            "company_id": company_id,
            "name": name,
            "size": len(data),
            "storage_path": path,
            "classification": classification,
            "uploaded_by": user_id,
        }).execute().data[0]
    except Exception:
        db.storage.from_(DOCUMENTS_BUCKET).remove([path])
        raise


def remove(doc: dict) -> None:
    db = get_db()
    try:
        db.storage.from_(DOCUMENTS_BUCKET).remove([doc["storage_path"]])
    except Exception:
        log.warning("Could not delete storage object %s", doc["storage_path"])
    db.table("documents").delete().eq("id", doc["id"]).execute()
