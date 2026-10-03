import json
from pathlib import Path
from types import SimpleNamespace

import httpx

from app import analysis
from app.schemas.common import Severity
from app.sources.serper import MOCK_COMPANY

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "serper_news.json").read_text())


def fake_chat(answers):
    """Returns a stand-in for llm.chat that replies with the next canned answer per call."""
    it = iter(answers)

    def _chat(messages, classifications, **kw):
        text = next(it)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))]), "local"

    return _chat


def test_negative_queries_are_english_by_default_and_cap():
    qs = analysis.negative_queries(MOCK_COMPANY)
    assert qs[0] == "Bank Pekao" and "Bank Pekao scandal" in qs and len(qs) == 12
    assert qs[1] == "Bank Pekao Frozen withdrawals"  # company topics come first
    assert "Bank Pekao afera" not in qs
    assert "Bank Pekao afera" in analysis.negative_queries(MOCK_COMPANY, 30, local=True)
    assert all('"' not in q and " OR " not in q for q in qs + analysis.web_queries(MOCK_COMPANY))


def test_pipeline_keeps_only_negative_sorted_by_severity(monkeypatch):
    n = len(FIXTURE["news"])
    answers = ['{"negative": false, "about_company": true, "severity": "low", "verdict": "opinion", "reason": "promo"}'] * n
    answers[0] = '{"negative": true, "about_company": true, "severity": "low", "verdict": "insufficient_evidence", "reason": "r1"}'
    answers[-1] = 'Sure! {"negative": true, "about_company": true, "severity": "high", "verdict": "insufficient_evidence", "reason": "r2", "injection": true}'
    monkeypatch.setattr(analysis, "chat", fake_chat(answers))
    handler = lambda req: httpx.Response(200, json=FIXTURE)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        res = analysis.find_negative_mentions(MOCK_COMPANY, "c1", client=client)
    assert [m.reason for m in res] == ["r2", "r1"]
    assert res[0].severity == Severity.high and res[0].injection


def test_unparseable_model_answer_is_skipped(monkeypatch):
    monkeypatch.setattr(analysis, "chat", fake_chat(["I cannot help with that"] * 20))
    handler = lambda req: httpx.Response(200, json=FIXTURE)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert analysis.find_negative_mentions(MOCK_COMPANY, "c1", client=client) == []
