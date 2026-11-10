from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from athena_api.app import create_app
from athena_api.sessions.service import SessionService
from athena_api.sessions.store import MemorySessionStore, SqliteSessionStore
from athena_api.srs.service import SrsService
from athena_api.srs.store import MemoryStore

UNIT = "cse5dmi-2026-s2"
BASE = f"/units/{UNIT}/sessions"


class Clock:
    def __init__(self):
        self.now = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)

    def __call__(self):
        self.now += timedelta(seconds=1)
        return self.now


@pytest.fixture(params=["memory", "sqlite"])
def client(request, tmp_path):
    store = MemorySessionStore() if request.param == "memory" else SqliteSessionStore(tmp_path / "s.db")
    who = {"id": "alice"}
    app = create_app(srs=SrsService(MemoryStore()), sessions=SessionService(store, clock=Clock()),
                     resolve_student=lambda _r: who["id"])
    c = TestClient(app)
    c.who = who
    return c


def create(client, goal="k-fold cross-validation"):
    r = client.post(BASE, json={"goal": goal})
    assert r.status_code == 201
    return r.json()


def test_create_opens_with_a_tutor_message_and_hides_student_id(client):
    data = create(client, "  k-fold   cross-validation ")
    s = data["session"]
    assert s["goal"] == "k-fold cross-validation" and s["title"] == s["goal"] and s["shared"] is False
    assert "student_id" not in s
    [opening] = data["messages"]
    assert opening["role"] == "tutor" and "k-fold cross-validation" in opening["content"]


def test_send_returns_learner_and_tutor_messages_and_persists(client):
    sid = create(client)["session"]["id"]
    learner, tutor = client.post(f"{BASE}/{sid}/messages", json={"text": "I know it splits data"}).json()
    assert (learner["role"], learner["content"], tutor["role"]) == ("learner", "I know it splits data", "tutor")
    messages = client.get(f"{BASE}/{sid}").json()["messages"]
    assert [m["role"] for m in messages] == ["tutor", "learner", "tutor"]


def test_list_is_most_recent_first_and_per_unit(client):
    a = create(client, "clustering")["session"]["id"]
    b = create(client, "overfitting")["session"]["id"]
    client.post(f"{BASE}/{a}/messages", json={"text": "hi"})  # bumps a
    assert [s["id"] for s in client.get(BASE).json()] == [a, b]
    assert client.get("/units/cse5alg-2026-s2/sessions").json() == []


def test_rename_and_delete(client):
    sid = create(client)["session"]["id"]
    assert client.patch(f"{BASE}/{sid}", json={"title": "CV basics"}).json()["title"] == "CV basics"
    assert client.patch(f"{BASE}/{sid}", json={"title": "   "}).status_code == 422
    assert client.delete(f"{BASE}/{sid}").status_code == 204
    assert client.get(f"{BASE}/{sid}").status_code == 404
    assert client.get(BASE).json() == []


def test_students_cannot_see_or_touch_each_others_sessions(client):
    sid = create(client)["session"]["id"]
    client.who["id"] = "bob"
    assert client.get(BASE).json() == []
    for r in [
        client.get(f"{BASE}/{sid}"),
        client.post(f"{BASE}/{sid}/messages", json={"text": "hello"}),
        client.patch(f"{BASE}/{sid}", json={"title": "mine now"}),
        client.delete(f"{BASE}/{sid}"),
    ]:
        assert r.status_code == 404
    client.who["id"] = "alice"
    assert client.get(f"{BASE}/{sid}").json()["session"]["title"] == "k-fold cross-validation"


def test_session_is_bound_to_its_unit(client):
    sid = create(client)["session"]["id"]
    assert client.get(f"/units/cse5alg-2026-s2/sessions/{sid}").status_code == 404


def test_validation_and_auth(client):
    assert client.post(BASE, json={"goal": ""}).status_code == 422
    assert client.post(BASE, json={"goal": "x", "student_id": "bob"}).status_code == 422
    sid = create(client)["session"]["id"]
    assert client.post(f"{BASE}/{sid}/messages", json={"text": "  "}).status_code == 422
    client.who["id"] = None
    assert client.get(BASE).status_code == 401
