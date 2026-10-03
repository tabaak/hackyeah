from app.schemas.common import CamelModel, MentionStatus, Platform, Severity, Verdict


class Cluster(CamelModel):
    size: int
    accounts: int


class Mention(CamelModel):
    id: str
    company_id: str
    platform: Platform
    author: str
    handle: str
    text: str
    at: int  # Unix ms
    severity: Severity
    verdict: Verdict
    reason: str
    reach: int
    cluster: Cluster | None = None
    injection: bool = False  # hidden prompt injection detected and blocked
    status: MentionStatus
    url: str | None = None  # link to the original post/article (news and Google results)
    avatar_url: str | None = None  # author's picture (source's own link)
    images: list[str] = []  # pictures attached to the post / article thumbnail


class MentionImport(CamelModel):
    url: str
    company_id: str


class MentionStatusUpdate(CamelModel):
    status: MentionStatus
