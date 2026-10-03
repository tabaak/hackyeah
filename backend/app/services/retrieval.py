"""Evidence retrieval from a company's documents. Restricted chunks are never returned."""
import re
from collections import Counter

from app.db import get_db
from app.services import llm

USABLE = ("public", "internal", "confidential")
STOPWORDS = set("""a an the and or but of to in on at for with from by is are was were be been it its this that these those
as not no yes we you they he she i our your their my me us them have has had do does did will would can could should
just about into over than then so if all any some more most very there here what which who when where why how""".split())


def _terms(text: str) -> Counter:
    return Counter(w for w in re.findall(r"[a-zA-ZÀ-ɏЀ-ӿ]{3,}", text.lower()) if w not in STOPWORDS)


def keyword_search(company_id: str, query: str, limit: int) -> list[dict]:
    db = get_db()
    docs = (
        db.table("documents").select("id, name, classification")
        .eq("company_id", company_id).eq("status", "ready").in_("classification", list(USABLE))
        .execute().data
    )
    if not docs:
        return []
    by_id = {d["id"]: d for d in docs}
    chunks = (
        db.table("document_chunks").select("id, document_id, content, classification")
        .in_("document_id", list(by_id)).neq("classification", "restricted")
        .execute().data
    )
    q = _terms(query)
    scored = []
    for c in chunks:
        terms = _terms(c["content"])
        score = sum(min(n, terms[w]) for w, n in q.items() if w in terms)
        if score:
            scored.append((score, c))
    scored.sort(key=lambda x: -x[0])
    return [
        {"chunk_id": c["id"], "document_id": c["document_id"], "name": by_id[c["document_id"]]["name"],
         "classification": c["classification"], "content": c["content"], "score": float(s)}
        for s, c in scored[:limit]
    ]


def vector_search(company_id: str, query: str, limit: int) -> list[dict] | None:
    vectors = llm.embed([query])
    if not vectors:
        return None
    rows = get_db().rpc("match_document_chunks", {
        "p_company_id": company_id,
        "p_query_embedding": llm.vector_literal(vectors[0]),
        "p_match_count": limit,
        "p_max_classification": "confidential",
    }).execute().data
    return [
        {"chunk_id": r["chunk_id"], "document_id": r["document_id"], "name": r["document_name"],
         "classification": r["classification"], "content": r["content"], "score": r["similarity"]}
        for r in rows
        if r["similarity"] is not None and r["similarity"] >= 0.25
    ]


def search(company_id: str, query: str, limit: int = 6) -> list[dict]:
    """Relevant chunks, best first. Vector search when embeddings are configured, else keyword overlap."""
    hits = vector_search(company_id, query, limit)
    if hits is None:
        hits = keyword_search(company_id, query, limit)
    return [h for h in hits if h["classification"] in USABLE]


def evidence_docs(hits: list[dict], limit: int = 3) -> list[dict]:
    """Distinct documents behind the hits, in rank order (API: response.evidence)."""
    seen: dict[str, dict] = {}
    for h in hits:
        if h["document_id"] not in seen:
            seen[h["document_id"]] = {"doc_id": h["document_id"], "name": h["name"], "classification": h["classification"]}
    return list(seen.values())[:limit]
