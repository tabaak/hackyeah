"""Request validation: bad enums, limits and bodies get 422 before reaching the (stub, 501) handlers."""
import pytest

from tests.conftest import API

COMPANY = {"name": "Kestrel Bank", "sector": "Banking", "country": "Poland"}
FULL_COMPANY = COMPANY | {"website": "https://kestrel.example", "aliases": ["Kestrel", "KSTL"],
                          "people": ["Jan Nowak (CEO)"], "topics": ["Frozen withdrawals", "Data breach"]}


def without(d, key):
    return {k: v for k, v in d.items() if k != key}


@pytest.mark.parametrize("query,status", [
    ("", 501),
    ("?company_id=c-1&severity=high&platform=news&status=new&limit=200&since_timestamp=1790000000000&since_id=m-1", 501),
    ("?limit=1", 501),
    ("?severity=critical", 422),
    ("?platform=instagram", 422),
    ("?status=archived", 422),
    ("?limit=0", 422),
    ("?limit=201", 422),
    ("?since_timestamp=yesterday", 422),
])
def test_mention_filters(client, analyst, query, status):
    assert client.get(f"{API}/mentions{query}", headers=analyst).status_code == status


@pytest.mark.parametrize("method,path", [("POST", "/companies"), ("PUT", "/companies/c-1")])
@pytest.mark.parametrize("body,status", [
    (COMPANY, 501),
    (FULL_COMPANY, 501),
    (without(COMPANY, "name"), 422),
    (without(COMPANY, "sector"), 422),
    (without(COMPANY, "country"), 422),
    (COMPANY | {"aliases": "Kestrel"}, 422),
    (COMPANY | {"topics": [1, 2]}, 422),
], ids=["minimal", "full", "no-name", "no-sector", "no-country", "aliases-not-list", "topics-not-strings"])
def test_company_body(client, analyst, method, path, body, status):
    assert client.request(method, API + path, headers=analyst, json=body).status_code == status


@pytest.mark.xfail(strict=True, reason=(
    "CompanyDraft.sector is free text, but the DB CHECK allows only Banking/Defence/Fintech/Energy/Other: "
    "a bad value passes the API and fails later at insert time (500). Fix: Literal/Enum for sector."))
def test_unknown_sector_rejected(client, analyst):
    assert client.post(f"{API}/companies", headers=analyst, json=COMPANY | {"sector": "Crypto"}).status_code == 422


@pytest.mark.parametrize("body,status", [
    ({"status": "dismissed"}, 501),
    ({"status": "responded"}, 501),
    ({"status": "new"}, 501),
    ({"status": "archived"}, 422),
    ({}, 422),
])
def test_mention_status_body(client, analyst, body, status):
    assert client.patch(f"{API}/mentions/m-1/status", headers=analyst, json=body).status_code == status


@pytest.mark.parametrize("body,status", [
    ({"classification": "confidential"}, 501),
    ({"classification": "restricted"}, 501),
    ({"classification": "secret"}, 422),
    ({}, 422),
])
def test_document_classification_body(client, analyst, body, status):
    assert client.patch(f"{API}/documents/d-1", headers=analyst, json=body).status_code == status


@pytest.mark.parametrize("files,classifications,status", [
    (["faq.txt"], ["internal"], 501),
    (["faq.txt", "report.pdf"], ["public", "confidential"], 501),
    ([], ["internal"], 422),
    (["faq.txt"], [], 422),
    (["faq.txt"], ["secret"], 422),
], ids=["one-file", "two-files", "no-files", "no-classification", "bad-classification"])
def test_document_upload(client, analyst, files, classifications, status):
    r = client.post(f"{API}/companies/c-1/documents", headers=analyst,
                    files=[("files", (name, b"Withdrawals work normally.", "text/plain")) for name in files],
                    data={"classifications": classifications})
    assert r.status_code == status, r.text


@pytest.mark.parametrize("platform,status", [
    ("news", 501), ("x", 501), ("facebook", 501), ("telegram", 501),
    ("instagram", 422), ("NEWS", 422),
])
def test_source_platform(client, analyst, platform, status):
    assert client.post(f"{API}/feed/sources/{platform}/sync", headers=analyst).status_code == status
    assert client.get(f"{API}/feed/sources/{platform}/status", headers=analyst).status_code == status


@pytest.mark.parametrize("body,status", [
    ({"text": "Withdrawals work normally."}, 501),
    ({"text": ""}, 501),
    ({}, 422),
    ({"text": 5}, 422),
])
def test_draft_body(client, analyst, body, status):
    assert client.patch(f"{API}/mentions/m-1/response/draft", headers=analyst, json=body).status_code == status


@pytest.mark.parametrize("body,status", [
    ({"approve": True}, 501),
    ({"approve": False, "comment": "Mentions a confidential figure"}, 501),
    ({}, 422),
    ({"approve": "maybe"}, 422),
])
def test_compliance_decision_body(client, compliance, body, status):
    assert client.post(f"{API}/mentions/m-1/response/decision", headers=compliance, json=body).status_code == status


@pytest.mark.parametrize("path", ["summary", "mentions-by-hour", "reach-by-platform", "claim-verification"])
def test_analytics_accepts_company_and_range(client, analyst, path):
    assert client.get(f"{API}/analytics/{path}?company_id=c-1&range=7d", headers=analyst).status_code == 501
