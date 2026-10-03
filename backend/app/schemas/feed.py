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


class MentionStatusUpdate(CamelModel):
    status: MentionStatus
