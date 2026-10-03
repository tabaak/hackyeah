"""Push notifications: device token registration and Expo push delivery for critical notifications."""
import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import push as routes
from app.services import notifications, push
from tests.test_companies import headers

TOKEN = "ExponentPushToken[abc123]"


class FakeDB:
    """Just enough of the Supabase client for push_tokens and notifications."""
    def __init__(self):
        self.rows = {"push_tokens": [], "notifications": [], "profiles": []}

    def table(self, name):
        return FakeQuery(self.rows[name])


class FakeQuery:
    def __init__(self, rows):
        self.rows, self.filters, self.op, self.payload = rows, [], "select", None

    def select(self, *_):
        return self

    def eq(self, key, value):
        self.filters.append(lambda r: r.get(key) == value)
        return self

    def in_(self, key, values):
        self.filters.append(lambda r: r.get(key) in values)
        return self

    def insert(self, payload):
        self.op, self.payload = "insert", payload
        return self

    def upsert(self, payload, on_conflict=None):
        assert on_conflict == "token"
        self.op, self.payload = "upsert", payload
        return self

    def delete(self):
        self.op = "delete"
        return self

    def execute(self):
        if self.op == "insert":
            rows = [{"id": f"n{len(self.rows) + i}", **r} for i, r in enumerate(self.payload)]
            self.rows.extend(rows)
            return SimpleNamespace(data=rows)
        if self.op == "upsert":
            self.rows[:] = [r for r in self.rows if r["token"] != self.payload["token"]]
            self.rows.append(dict(self.payload))
            return SimpleNamespace(data=[self.payload])
        matches = [r for r in self.rows if all(f(r) for f in self.filters)]
        if self.op == "delete":
            self.rows[:] = [r for r in self.rows if r not in matches]
        return SimpleNamespace(data=matches)


@pytest.fixture
def db(monkeypatch):
    fake = FakeDB()
    for module in (routes, push, notifications):
        monkeypatch.setattr(module, "get_db", lambda: fake)
    return fake


@pytest.fixture
def expo(monkeypatch):
    """Records messages sent to the Expo push API; `tickets` sets the per-message reply."""
    sent, state = [], {"tickets": None, "fail": False}

    def handler(req: httpx.Request) -> httpx.Response:
        if state["fail"]:
            raise httpx.ConnectError("expo down")
        assert str(req.url) == push.EXPO_PUSH_URL
        batch = json.loads(req.content)
        sent.extend(batch)
        return httpx.Response(200, json={"data": state["tickets"] or [{"status": "ok", "id": "t"} for _ in batch]})

    monkeypatch.setattr(push, "_http", httpx.Client(transport=httpx.MockTransport(handler)))
    return SimpleNamespace(sent=sent, state=state)


def test_device_token_is_registered_for_the_caller_and_moves_with_sign_in(db):
    with TestClient(app) as client:
        r = client.post("/api/v1/push-tokens", json={"token": TOKEN, "platform": "ios"}, headers=headers(user="u1"))
        assert r.status_code == 204
        # Same device, other account: the token now belongs only to the new user
        client.post("/api/v1/push-tokens", json={"token": TOKEN, "platform": "ios"}, headers=headers(user="u2"))
    assert [(t["token"], t["user_id"], t["organization_id"]) for t in db.rows["push_tokens"]] == [(TOKEN, "u2", "o1")]


def test_only_expo_push_tokens_are_accepted(db):
    with TestClient(app) as client:
        r = client.post("/api/v1/push-tokens", json={"token": "not-a-token", "platform": "ios"}, headers=headers())
    assert r.status_code == 422 and db.rows["push_tokens"] == []


def test_unregister_removes_only_the_callers_token(db):
    db.rows["push_tokens"] += [{"token": TOKEN, "user_id": "u1"}, {"token": "ExponentPushToken[other]", "user_id": "u2"}]
    with TestClient(app) as client:
        # Someone else cannot remove u1's device
        assert client.delete(f"/api/v1/push-tokens/{TOKEN}", headers=headers(user="u2")).status_code == 204
        assert len(db.rows["push_tokens"]) == 2
        assert client.delete(f"/api/v1/push-tokens/{TOKEN}", headers=headers(user="u1")).status_code == 204
    assert [t["token"] for t in db.rows["push_tokens"]] == ["ExponentPushToken[other]"]


def test_critical_notification_is_pushed_to_every_device_of_its_recipients(db, expo):
    db.rows["push_tokens"] += [
        {"token": "ExponentPushToken[phone]", "user_id": "u1"},
        {"token": "ExponentPushToken[tablet]", "user_id": "u1"},
        {"token": "ExponentPushToken[stranger]", "user_id": "u9"},
    ]
    notifications.notify("o1", "critical_mention", "Bank run rumour on X", "high", "m1", user_ids=["u1"])

    assert sorted(m["to"] for m in expo.sent) == ["ExponentPushToken[phone]", "ExponentPushToken[tablet]"]
    message = expo.sent[0]
    assert message["title"] == "Critical mention"
    assert message["body"] == "Bank run rumour on X"
    assert message["data"] == {"kind": "critical_mention", "mentionId": "m1"}
    assert message["priority"] == "high" and message["sound"] == "default"
    assert len(db.rows["notifications"]) == 1  # the in-app notification is still stored


@pytest.mark.parametrize("kind", ["approval_requested", "approval_decided"])
def test_non_critical_kinds_are_not_pushed(db, expo, kind):
    db.rows["push_tokens"].append({"token": TOKEN, "user_id": "u1"})
    notifications.notify("o1", kind, "Approval", "high", "m1", user_ids=["u1"])
    assert expo.sent == []


def test_tokens_of_uninstalled_apps_are_dropped(db, expo):
    db.rows["push_tokens"] += [{"token": "ExponentPushToken[gone]", "user_id": "u1"}, {"token": TOKEN, "user_id": "u1"}]
    expo.state["tickets"] = [
        {"status": "error", "message": "not registered", "details": {"error": "DeviceNotRegistered"}},
        {"status": "ok", "id": "t"},
    ]
    notifications.notify("o1", "critical_mention", "Rumour", "high", "m1", user_ids=["u1"])
    assert [t["token"] for t in db.rows["push_tokens"]] == [TOKEN]


def test_push_failure_never_breaks_notify(db, expo):
    db.rows["push_tokens"].append({"token": TOKEN, "user_id": "u1"})
    expo.state["fail"] = True
    notifications.notify("o1", "critical_mention", "Rumour", "high", "m1", user_ids=["u1"])
    assert len(db.rows["notifications"]) == 1


def test_long_titles_are_shortened_for_the_lock_screen(db, expo):
    db.rows["push_tokens"].append({"token": TOKEN, "user_id": "u1"})
    notifications.notify("o1", "critical_mention", "x" * 500, "high", None, user_ids=["u1"])
    assert len(expo.sent[0]["body"]) <= 180
