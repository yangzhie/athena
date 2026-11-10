import pytest
from fastapi.testclient import TestClient

from athena_api.app import create_app
from athena_api.lectures.service import LectureService
from athena_api.lectures.store import MemoryLectureStore
from athena_api.sessions.service import SessionService
from athena_api.sessions.store import MemorySessionStore, SqliteSessionStore
from athena_api.srs.service import SrsService
from athena_api.srs.store import MemoryStore

UNIT = "cse5dmi-2026-s2"
MINE = f"/units/{UNIT}/sessions"
SHARED = f"/units/{UNIT}/shared-sessions"


@pytest.fixture(params=["memory", "sqlite"])
def client(request, tmp_path):
    store = MemorySessionStore() if request.param == "memory" else SqliteSessionStore(tmp_path / "s.db")
    who = {"student": "alice-12345", "lecturer": "dr-liu"}
    app = create_app(srs=SrsService(MemoryStore()), sessions=SessionService(store), lectures=LectureService(MemoryLectureStore()),
                     resolve_student=lambda _r: who["student"], resolve_lecturer=lambda _r, _o: who["lecturer"])
    c = TestClient(app)
    c.who = who
    return c


def start(client, goal="k-fold cross-validation"):
    sid = client.post(MINE, json={"goal": goal}).json()["session"]["id"]
    client.post(f"{MINE}/{sid}/messages", json={"text": "I get confused about the folds"})
    return sid


def test_lecturer_sees_only_shared_sessions_anonymously(client):
    shared_sid = start(client)
    start(client, "clustering")  # private
    client.post(f"{MINE}/{shared_sid}/share")

    [summary] = client.get(SHARED).json()
    assert summary["student_label"] == "Anonymous student"
    assert summary["goal"] == "k-fold cross-validation" and summary["message_count"] == 3

    view = client.get(f"{SHARED}/{summary['share_id']}")
    body = view.text
    assert view.status_code == 200
    assert "alice-12345" not in body  # no student id anywhere
    assert shared_sid not in body  # no stable session id either
    assert [m["role"] for m in view.json()["messages"]] == ["tutor", "learner", "tutor"]


def test_stopping_sharing_ends_access_immediately(client):
    sid = start(client)
    client.post(f"{MINE}/{sid}/share")
    [summary] = client.get(SHARED).json()
    client.delete(f"{MINE}/{sid}/share")
    assert client.get(SHARED).json() == []
    assert client.get(f"{SHARED}/{summary['share_id']}").status_code == 404


def test_resharing_gives_a_new_unlinkable_id(client):
    sid = start(client)
    client.post(f"{MINE}/{sid}/share")
    first = client.get(SHARED).json()[0]
    first_ids = {m["id"] for m in client.get(f"{SHARED}/{first['share_id']}").json()["messages"]}
    client.delete(f"{MINE}/{sid}/share")
    client.post(f"{MINE}/{sid}/share")
    second = client.get(SHARED).json()[0]
    assert second["share_id"] != first["share_id"]
    assert client.get(f"{SHARED}/{first['share_id']}").status_code == 404
    second_ids = {m["id"] for m in client.get(f"{SHARED}/{second['share_id']}").json()["messages"]}
    assert not first_ids & second_ids


def test_only_lecturers_of_that_unit(client):
    sid = start(client)
    client.post(f"{MINE}/{sid}/share")
    share_id = client.get(SHARED).json()[0]["share_id"]
    assert client.get(f"/units/cse5alg-2026-s2/shared-sessions/{share_id}").status_code == 404  # other unit
    client.who["lecturer"] = None
    assert client.get(SHARED).status_code == 403
    assert client.get(f"{SHARED}/{share_id}").status_code == 403
