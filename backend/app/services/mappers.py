"""Database rows -> API models (camelCase JSON, Unix ms)."""
from app.schemas.common import Role
from app.schemas.companies import Company
from app.schemas.documents import Doc
from app.schemas.feed import Cluster, Mention
from app.services.timeutil import to_ms

COMPANY_SELECT = "*, documents(id, name, size, classification, status, summary, created_at)"
MENTION_SELECT = "*, clusters(size, unique_authors)"


def doc(row: dict, role: Role) -> Doc:
    """A summary reveals the content, so restricted summaries follow GET /documents/{id}/url: compliance only."""
    visible = row["classification"] != "restricted" or role == Role.compliance
    return Doc(id=row["id"], name=row["name"], size=row["size"], classification=row["classification"], status=row["status"],
               summary=row.get("summary") if visible else None)


def company(row: dict, role: Role) -> Company:
    docs = sorted(row.get("documents") or [], key=lambda d: d.get("created_at") or "")
    return Company(
        id=row["id"], name=row["name"], website=row["website"], aliases=row["aliases"], sector=row["sector"],
        country=row["country"], people=row["people"], topics=row["topics"],
        documents=[doc(d, role) for d in docs], created_at=to_ms(row["created_at"]),
    )


def mention(row: dict) -> Mention:
    c = row.get("clusters")
    return Mention(
        id=row["id"], company_id=row["company_id"], platform=row["platform"], author=row["author"], handle=row["handle"],
        text=row["text"], at=to_ms(row["published_at"]), severity=row["severity"], verdict=row["verdict"],
        reason=row["reason"], reach=row["reach"],
        cluster=Cluster(size=c["size"], accounts=c["unique_authors"]) if c else None,
        injection=row["injection_suspected"], status=row["status"], url=row.get("url"),
    )
