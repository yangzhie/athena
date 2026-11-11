"""Answer retries use real orchestration with explicitly selected offline fixtures."""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
import sqlite3

import pytest
from athena_agent.llm import MockLLM
from athena_agent.sqlite_memory import SQLiteLearningMemory
from .http_client import TestClient

from athena_api.app import create_app
from athena_api.lectures.service import LectureService
from athena_api.lectures.store import MemoryLectureStore
from athena_api.sessions.agent_tutor import AgentTutor
from athena_api.sessions.models import AnswerReceipt, LearningSession, Message
from athena_api.sessions.service import SessionService
from athena_api.sessions.store import AnswerConflict, MemorySessionStore, SqliteSessionStore
from athena_api.srs.service import SrsService
from athena_api.srs.store import MemoryStore

FIXTURE = json.loads((Path(__file__).parents[3] / "agent/tests/fixtures/api_journey.json").read_text())
OFFERING = "cse5alg-2026-s2"
BASE = f"/units/{OFFERING}/sessions"


@pytest.fixture(params=["memory", "sqlite"])
def host(request, tmp_path):
    store = MemorySessionStore() if request.param == "memory" else SqliteSessionStore(tmp_path / "host.db")
    yield store
    if isinstance(store, SqliteSessionStore):
        store.close()


def client_for(host, agent, responses):
    mock = MockLLM(responses)
    who = {"id": "alice"}
    service = SessionService(host, AgentTutor(agent, mock))
    client = TestClient(create_app(srs=SrsService(MemoryStore()), sessions=service,
                                   lectures=LectureService(MemoryLectureStore()),
                                   resolve_student=lambda _r: who["id"]))
    return client, mock, who


def start(client):
    response = client.post(BASE, json={"goal": FIXTURE["goal"]})
    assert response.status_code == 201, response.text
    data = response.json()
    return data["session"]["id"], data["messages"][0]["activity"]


def body_for(activity, turn):
    return {"question_id": activity["question"]["question_id"], "shown": str(turn["value"]),
            **({"choice_id": turn["value"]} if turn["kind"] == "choice" else {"text": turn["value"]})}


def test_retries_after_later_turns_return_original_messages_without_regrading(host, tmp_path):
    with SQLiteLearningMemory(tmp_path / "agent.db") as agent:
        client, mock, who = client_for(host, agent, FIXTURE["responses"])
        sid, activity = start(client)
        receipts = []
        for turn in FIXTURE["turns"]:
            if turn["kind"] == "continue":
                response = client.post(f"{BASE}/{sid}/continue", json={"activity_id": activity["activity_id"]})
            else:
                body = body_for(activity, turn)
                response = client.post(f"{BASE}/{sid}/answers", json=body)
                receipts.append((body, response.json()))
            assert response.status_code == 200, response.text
            activity = response.json()[-1]["activity"]
        before = client.get(f"{BASE}/{sid}").json()
        calls = len(mock.calls)
        for body, original in receipts:
            # Display labels aren't grading input and cannot rewrite accepted history.
            response = client.post(f"{BASE}/{sid}/answers", json={**body, "shown": "Changed label"})
            assert response.status_code == 200 and response.json() == original
            if "text" in body:
                assert client.post(f"{BASE}/{sid}/answers", json={**body, "text": f"  {body['text']}  "}).json() == original
            for change in [{"hint_used": True}, ({"choice_id": "different"} if "choice_id" in body else {"text": "different"})]:
                assert client.post(f"{BASE}/{sid}/answers", json={**body, **change}).status_code == 409
        assert len(mock.calls) == calls
        assert client.get(f"{BASE}/{sid}").json() == before
        body = receipts[0][0]
        who["id"] = "bob"
        assert client.post(f"{BASE}/{sid}/answers", json=body).status_code == 404
        assert host.answer_receipt("bob", sid, body["question_id"]) is None
        who["id"] = "alice"
        assert client.post(f"/units/other/sessions/{sid}/answers", json=body).status_code == 404
        assert client.delete(f"{BASE}/{sid}").status_code == 204
        assert host.answer_receipt("alice", sid, body["question_id"]) is None


def test_receipt_survives_host_and_agent_restart(tmp_path):
    host_path, agent_path = tmp_path / "host.db", tmp_path / "agent.db"
    host = SqliteSessionStore(host_path)
    with SQLiteLearningMemory(agent_path) as agent:
        client, _, _ = client_for(host, agent, FIXTURE["responses"])
        sid, activity = start(client)
        body = body_for(activity, FIXTURE["turns"][0])
        original = client.post(f"{BASE}/{sid}/answers", json=body)
        assert original.status_code == 200
    host.close()
    reopened = SqliteSessionStore(host_path)
    with SQLiteLearningMemory(agent_path) as agent:
        client, mock, _ = client_for(reopened, agent, [])
        assert client.post(f"{BASE}/{sid}/answers", json=body).json() == original.json()
        assert mock.calls == []
    reopened.close()


def test_host_storage_failure_rolls_back_exchange_and_retry_reconciles_agent(tmp_path):
    host_path, agent_path = tmp_path / "host.db", tmp_path / "agent.db"
    host = SqliteSessionStore(host_path)
    with SQLiteLearningMemory(agent_path) as agent:
        client, _, _ = client_for(host, agent, FIXTURE["responses"])
        sid, activity = start(client)
        body = body_for(activity, FIXTURE["turns"][0])
        before = client.get(f"{BASE}/{sid}").json()
        # Fail after message and timestamp writes, while committing the receipt.
        with sqlite3.connect(host_path) as db:
            db.execute("CREATE TRIGGER fail_receipt BEFORE INSERT ON session_answers BEGIN SELECT RAISE(ABORT, 'disk failure'); END")
        failed = client.post(f"{BASE}/{sid}/answers", json=body)
        assert failed.status_code == 503 and "disk failure" not in failed.text
        assert client.get(f"{BASE}/{sid}").json() == before
        assert host.answer_receipt("alice", sid, body["question_id"]) is None
    host.close()
    with sqlite3.connect(host_path) as db:
        db.execute("DROP TRIGGER fail_receipt")
    reopened = SqliteSessionStore(host_path)
    with SQLiteLearningMemory(agent_path) as agent:
        client, mock, _ = client_for(reopened, agent, [])
        response = client.post(f"{BASE}/{sid}/answers", json=body)
        assert response.status_code == 200, response.text
        assert len(response.json()) == 3 and mock.calls == []
        assert client.post(f"{BASE}/{sid}/answers", json=body).json() == response.json()
        assert len(client.get(f"{BASE}/{sid}").json()["messages"]) == 4
    reopened.close()


def test_simultaneous_host_answers_publish_one_exchange(host):
    class Tutor:
        async def answer(self, *_args, **_kwargs):
            from athena_api.sessions.tutor import TutorReply
            entered.append(True)
            if len(entered) == 2:
                both.set()
            await both.wait()
            return [TutorReply("Next step")]

    now = datetime.now(UTC)
    host.put(LearningSession(id="s", student_id="alice", offering_id=OFFERING, goal="Goal", title="Goal",
                             created_at=now, updated_at=now))
    entered = []

    async def run():
        nonlocal both
        both = asyncio.Event()
        service = SessionService(host, Tutor())
        return await asyncio.gather(*[service.answer("alice", OFFERING, "s", "q", choice_id="a", text=None, shown="A") for _ in range(2)])

    both = None
    first, second = asyncio.run(run())
    assert first == second
    assert host.messages("alice", "s") == first


def test_competing_sqlite_connections_keep_the_first_receipt(tmp_path):
    path = tmp_path / "host.db"
    first, second = SqliteSessionStore(path), SqliteSessionStore(path)
    now = datetime.now(UTC)
    first.put(LearningSession(id="s", student_id="alice", offering_id=OFFERING, goal="Goal", title="Goal",
                              created_at=now, updated_at=now))
    def receipt(message_id):
        return AnswerReceipt(question_id="q", choice_id="a", text=None, hint_used=False, messages=[
            Message(id=message_id, session_id="s", role="learner", content="A", answer_for="q", created_at=now),
        ])
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda item: item[0].complete_answer("alice", "s", receipt(item[1]), now),
                                [(first, "one"), (second, "two")]))
    assert results[0] == results[1] == first.messages("alice", "s")
    with pytest.raises(AnswerConflict):
        second.complete_answer("alice", "s", receipt("three").model_copy(update={"choice_id": "b"}), now)
    first.close()
    second.close()


def test_legacy_answer_cannot_be_duplicated_and_unaccepted_questions_leave_no_receipt(host, tmp_path):
    with SQLiteLearningMemory(tmp_path / "agent.db") as agent:
        client, mock, _ = client_for(host, agent, FIXTURE["responses"])
        sid, activity = start(client)
        calls = len(mock.calls)
        body = body_for(activity, FIXTURE["turns"][0])
        # Simulate an exchange saved by an older release without retry metadata.
        host.add_message("alice", Message(id="old", session_id=sid, role="learner", content="Old answer",
                                          answer_for=body["question_id"], created_at=datetime.now(UTC)))
        before = client.get(f"{BASE}/{sid}").json()
        response = client.post(f"{BASE}/{sid}/answers", json=body)
        assert response.status_code == 409 and "Refresh" in response.json()["detail"]
        assert len(mock.calls) == calls and client.get(f"{BASE}/{sid}").json() == before
        assert client.post(f"{BASE}/{sid}/answers", json={**body, "question_id": "unknown"}).status_code == 400
        assert host.answer_receipt("alice", sid, "unknown") is None
        assert client.get(f"{BASE}/{sid}").json() == before


def test_retry_during_host_commit_is_not_mistaken_for_legacy_answer(host, monkeypatch):
    now = datetime.now(UTC)
    host.put(LearningSession(id="s", student_id="alice", offering_id=OFFERING, goal="Goal", title="Goal",
                             created_at=now, updated_at=now))
    receipt = AnswerReceipt(question_id="q", choice_id="a", text=None, hint_used=False, messages=[
        Message(id="answer", session_id="s", role="learner", content="A", answer_for="q", created_at=now),
        Message(id="reply", session_id="s", role="tutor", content="Next step", created_at=now),
    ])
    messages = host.messages

    def complete_while_reading_history(student_id, session_id):
        host.complete_answer("alice", "s", receipt, now)
        return messages(student_id, session_id)

    monkeypatch.setattr(host, "messages", complete_while_reading_history)
    result = asyncio.run(SessionService(host).answer("alice", OFFERING, "s", "q", choice_id="a", text=None, shown="A"))
    assert result == receipt.messages
