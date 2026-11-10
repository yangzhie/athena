"""Offline recovery checks use real agent transitions, routes and durable stores."""

import asyncio
import sqlite3

import pytest
from athena_agent.contracts import RequestContext
from athena_agent.llm import DependencyError
from athena_agent.sqlite_memory import SQLiteLearningMemory

from athena_api.sessions.operations import Operation
from athena_api.sessions.store import MemorySessionStore, SqliteSessionStore
from athena_api.sessions.service import SessionService
from .test_answer_retries import BASE, OFFERING, FIXTURE, body_for, client_for, start
from .test_agent_tutor import supply_materials


@pytest.mark.parametrize("kind", ["start", "message", "continue"])
def test_interrupted_host_write_reconciles_after_both_stores_restart(tmp_path, kind):
    host_path, agent_path = tmp_path / "host.db", tmp_path / "agent.db"
    host = SqliteSessionStore(host_path)
    with SQLiteLearningMemory(agent_path) as agent:
        client, mock, _ = client_for(host, agent, FIXTURE["responses"])
        headers = {"Idempotency-Key": "retry-operation"}
        payload = {"goal": FIXTURE["goal"]}
        path = BASE
        sid = None
        if kind != "start":
            sid, activity = start(client)
            if kind == "continue":
                asyncio.run(supply_materials(agent, "alice", sid))
                response = client.post(f"{BASE}/{sid}/answers", json=body_for(activity, FIXTURE["turns"][0]))
                assert response.status_code == 200
                activity = response.json()[-1]["activity"]
                path, payload = f"{BASE}/{sid}/continue", {"activity_id": activity["activity_id"]}
            else:
                # Explicit fixture for conversational routing and a clarification.
                client, mock, _ = client_for(host, agent, [
                    {"intent": "clarification"},
                    {"text": "Compare adjacent values."},
                ])
                path, payload = f"{BASE}/{sid}/messages", {"text": "Explain that"}
        before = client.get(BASE if sid is None else f"{BASE}/{sid}").json()
        with sqlite3.connect(host_path) as db:
            # Fail after inserting messages and updating the session, on final journal publication.
            db.execute("CREATE TRIGGER fail_publish BEFORE UPDATE ON session_operations WHEN NEW.complete=1 BEGIN SELECT RAISE(ABORT, 'interrupted write'); END")
        failed = client.post(path, json=payload, headers=headers)
        assert failed.status_code == 503 and "interrupted write" not in failed.text
        assert client.get(BASE if sid is None else f"{BASE}/{sid}").json() == before
        pending = host._db.execute("SELECT data FROM session_operations WHERE complete=0").fetchall()
        assert len(pending) == 1
        operation = Operation.model_validate_json(pending[0][0])
        sid = operation.session.id
        context = RequestContext(request_id="inspect", learner_id="alice", session_id=sid)
        snapshot = agent.read(context)
        receipt = snapshot.operation_results[operation.id]
        assert "operation_results" not in agent.load_conversation(context).model_dump()
        assert "operation_results" not in agent.load_learning(context).model_dump()
        assert mock.calls  # A real offline model-driven transition occurred.
    host.close()
    with sqlite3.connect(host_path) as db:
        db.execute("DROP TRIGGER fail_publish")
    host = SqliteSessionStore(host_path)
    with SQLiteLearningMemory(agent_path) as agent:
        client, mock, who = client_for(host, agent, [])
        if kind != "start":
            assert client.post(f"{BASE}/{sid}/messages", json={"text": "new"}, headers={"Idempotency-Key": "different"}).status_code == 409
        assert client.post(f"/units/other/sessions/operations/{operation.id}/retry").status_code == 404
        who["id"] = "bob"
        assert client.post(f"{BASE}/operations/{operation.id}/retry").status_code == 404
        who["id"] = "alice"
        recovered = client.post(f"{BASE}/operations/{operation.id}/retry")
        assert recovered.status_code == 200
        response = client.post(path, json=payload, headers=headers)
        assert response.status_code == (201 if kind == "start" else 200), response.text
        messages = response.json()["messages"] if kind == "start" else response.json()
        assert recovered.json()["messages"] == messages
        replies = [m for m in messages if m["role"] == "tutor"]
        assert replies[0]["content"] == receipt["replies"][0]["content"]
        assert client.post(path, json=payload, headers=headers).json() == response.json()
        assert agent.read(context) == snapshot
        assert mock.calls == []
        changed = {"goal": "different"} if kind == "start" else {"text": "different"}
        if kind != "continue":
            assert client.post(path, json=changed, headers=headers).status_code == 409
        who["id"] = "bob"
        if kind != "start":
            assert client.post(path, json=payload, headers=headers).status_code == 404
        else:
            # The same request ID grants no access to another learner's receipt.
            assert host.operation("bob", OFFERING, operation.id) is None
        who["id"] = "alice"
        assert "operation_results" not in client.get(f"{BASE}/{sid}").text
        assert client.delete(f"{BASE}/{sid}").status_code == 204
        assert host.operation("alice", OFFERING, operation.id) is None
    host.close()


def test_dependency_failure_stays_pending_and_retries_same_creation(tmp_path):
    host = MemorySessionStore()
    with SQLiteLearningMemory(tmp_path / "agent.db") as agent:
        client, _, _ = client_for(host, agent, [DependencyError("offline failure", retryable=False)])
        headers = {"Idempotency-Key": "start-again"}
        assert client.post(BASE, json={"goal": FIXTURE["goal"]}, headers=headers).status_code == 503
        assert client.get(BASE).json() == []
        pending = host.operation("alice", OFFERING, "start:start-again")
        assert pending and not pending.complete
        client, _, _ = client_for(host, agent, FIXTURE["responses"])
        response = client.post(BASE, json={"goal": FIXTURE["goal"]}, headers=headers)
        assert response.status_code == 201
        assert response.json()["session"]["id"] == pending.session.id
        # Without a reused key, even the same goal starts a fresh conversation.
        client, _, _ = client_for(host, agent, FIXTURE["responses"])
        fresh = client.post(BASE, json={"goal": FIXTURE["goal"]})
        assert fresh.status_code == 201
        assert fresh.json()["session"]["id"] != pending.session.id
        assert len(fresh.json()["messages"]) == 1
        assert fresh.json()["messages"][0]["activity"]["activity_id"] != response.json()["messages"][0]["activity"]["activity_id"]
        assert len(host.list("alice", OFFERING)) == 2


@pytest.mark.parametrize("storage", [MemorySessionStore, SqliteSessionStore])
def test_rejected_answer_can_be_corrected_without_blocking_session(storage, tmp_path):
    host = storage() if storage is MemorySessionStore else storage(tmp_path / "host.db")
    with SQLiteLearningMemory(tmp_path / "agent.db") as agent:
        client, _, _ = client_for(host, agent, FIXTURE["responses"])
        sid, activity = start(client)
        body = body_for(activity, FIXTURE["turns"][0])
        assert client.post(f"{BASE}/{sid}/answers", json={**body, "choice_id": "invalid"}).status_code == 400
        assert client.post(f"{BASE}/{sid}/answers", json=body).status_code == 200
    if isinstance(host, SqliteSessionStore):
        host.close()


def test_simultaneous_creation_reuses_the_reserved_session():
    from athena_api.sessions.tutor import TutorReply
    entered = []
    async def run():
        both = asyncio.Event()
        class Tutor:
            async def start(self, session):
                entered.append(session.id)
                if len(entered) == 2:
                    both.set()
                await both.wait()
                return [TutorReply("opening")]
        host = MemorySessionStore()
        service = SessionService(host, Tutor())
        results = await asyncio.gather(*[service.create("alice", OFFERING, "Goal", "same") for _ in range(2)])
        assert results[0] == results[1]
        assert len(host.list("alice", OFFERING)) == 1
        assert entered[0] == entered[1]
    asyncio.run(run())


@pytest.mark.parametrize('kind', ['start', 'message', 'answer', 'continue'])
def test_independent_adapters_publish_one_transition_and_exchange(tmp_path, kind):
    from athena_agent.llm import MockLLM
    from athena_api.sessions.agent_tutor import AgentTutor
    host_path, agent_path = tmp_path / 'host.db', tmp_path / 'agent.db'
    first, second = SqliteSessionStore(host_path), SqliteSessionStore(host_path)
    with SQLiteLearningMemory(agent_path) as agent1, SQLiteLearningMemory(agent_path) as agent2:
        client, _, _ = client_for(first, agent1, FIXTURE['responses'])
        responses = FIXTURE['responses']
        sid = None
        if kind != 'start':
            sid, activity = start(client)
            if kind == 'message':
                responses = [{'intent': 'clarification'}, {'text': 'Compare adjacent values.'}]
            else:
                asyncio.run(supply_materials(agent1, 'alice', sid))
                if kind == 'continue':
                    response = client.post(f'{BASE}/{sid}/answers', json=body_for(activity, FIXTURE['turns'][0]))
                    assert response.status_code == 200
                    activity = response.json()[-1]['activity']
                    responses = FIXTURE['responses'][8:10]
                else:
                    responses = FIXTURE['responses'][4:8]

        async def run():
            entered = 0
            both = asyncio.Event()
            class Provider:
                def __init__(self):
                    self.mock = MockLLM(responses)
                    self.first = True
                async def generate(self, messages, model):
                    nonlocal entered
                    if self.first:
                        self.first = False
                        entered += 1
                        if entered == 2:
                            both.set()
                        await both.wait()
                    return await self.mock.generate(messages, model)
            async def invoke(host, agent):
                service = SessionService(host, AgentTutor(agent, Provider()))
                if kind == 'start':
                    return await service.create('alice', OFFERING, FIXTURE['goal'], 'concurrent')
                if kind == 'message':
                    return await service.send('alice', OFFERING, sid, 'Explain that', 'concurrent')
                if kind == 'answer':
                    return await service.answer('alice', OFFERING, sid, activity['question']['question_id'], choice_id='b', text=None, shown='B')
                return await service.continue_('alice', OFFERING, sid, activity['activity_id'])
            return await asyncio.wait_for(asyncio.gather(invoke(first, agent1), invoke(second, agent2)), timeout=10)

        one, two = asyncio.run(run())
        assert one == two
        if kind == 'start':
            sid = one[0].id
        assert len(first.list('alice', OFFERING)) == 1
        context = RequestContext(request_id='inspect', learner_id='alice', session_id=sid)
        snapshot = agent1.read(context)
        assert len(first.messages('alice', sid)) == {'start': 1, 'message': 3, 'answer': 3, 'continue': 4}[kind]
        if kind in {'answer', 'continue'}:
            assert len(snapshot.active_topic.assessment_records) == 1
        assert len(snapshot.history) == (1 if kind in {'answer', 'message', 'continue'} else 0)
    first.close()
    second.close()


def test_failed_agent_publication_keeps_creation_pending_without_partial_state(tmp_path):
    host = SqliteSessionStore(tmp_path / 'host.db')
    path = tmp_path / 'agent.db'
    with SQLiteLearningMemory(path) as agent:
        client, _, _ = client_for(host, agent, FIXTURE['responses'])
        with sqlite3.connect(path) as db:
            db.execute("CREATE TRIGGER fail_agent BEFORE INSERT ON learning_sessions BEGIN SELECT RAISE(ABORT, 'agent disk failure'); END")
        headers = {'Idempotency-Key': 'agent-failure'}
        response = client.post(BASE, json={'goal': FIXTURE['goal']}, headers=headers)
        assert response.status_code == 503 and 'agent disk failure' not in response.text
        assert client.get(BASE).json() == []
        assert agent._db.execute('SELECT count(*) FROM learning_sessions').fetchone()[0] == 0
        pending = host.operation('alice', OFFERING, 'start:agent-failure')
        assert pending and not pending.complete
    with sqlite3.connect(path) as db:
        db.execute('DROP TRIGGER fail_agent')
    with SQLiteLearningMemory(path) as agent:
        client, mock, _ = client_for(host, agent, FIXTURE['responses'])
        response = client.post(f'{BASE}/operations/start:agent-failure/retry')
        assert response.status_code == 200
        assert response.json()['session']['id'] == pending.session.id
        assert len(response.json()['messages']) == 1
        assert mock.calls
    host.close()
