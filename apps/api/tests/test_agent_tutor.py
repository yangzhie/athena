"""The agent wired in as the tutor, driven through our sessions API.

Replays the agent's own scripted journey (agent/tests/fixtures/api_journey.json):
real orchestration, scripted LLM responses, no network.
"""

import json
from pathlib import Path

import pytest
from athena_agent.contracts import RequestContext
from athena_agent.conversation import InMemoryConversationStore
from athena_agent.knowledge import KnowledgeService
from athena_agent.llm import DependencyError, MockLLM
from athena_agent.memory import LearnerScopedMemory
from athena_agent.reliable_llm import ReliableLLM, RetryPolicy
from athena_agent.retrieval import MockRetriever
from .http_client import TestClient

from athena_api.app import create_app
from athena_api.sessions.agent_tutor import AgentTutor
from athena_api.sessions.tutor import PlaceholderTutor
from athena_api.sessions.service import SessionService
from athena_api.sessions.store import MemorySessionStore
from athena_api.srs.service import SrsService
from athena_api.srs.store import MemoryStore

FIXTURE = json.loads((Path(__file__).parents[3] / "agent/tests/fixtures/api_journey.json").read_text())
BASE = "/units/cse5alg-2026-s2/sessions"


def make_client(responses, host_store=None):
    agent_store = InMemoryConversationStore()
    tutor = AgentTutor(agent_store, ReliableLLM(MockLLM(responses), policy=RetryPolicy(max_attempts=1)))
    who = {"id": "alice"}
    app = create_app(srs=SrsService(MemoryStore()), sessions=SessionService(host_store or MemorySessionStore(), tutor=tutor),
                     resolve_student=lambda _r: who["id"])
    return TestClient(app), agent_store, who


async def supply_materials(agent_store, student, session_id):
    """What the agent's own journey does after start: retrieve the fixture's materials."""
    context = RequestContext(request_id="r", learner_id=student, session_id=session_id)
    await KnowledgeService(LearnerScopedMemory(agent_store, student), MockRetriever([FIXTURE["materials"]])).retrieve(
        context, FIXTURE["goal"]
    )


def test_full_learning_journey_through_sessions_api():
    import asyncio

    client, agent_store, _ = make_client(FIXTURE["responses"])
    created = client.post(BASE, json={"goal": FIXTURE["goal"]}).json()
    sid = created["session"]["id"]
    [opening] = created["messages"]
    assert opening["activity"]["kind"] == "question"  # the tutor asks first
    assert opening["content"] == opening["activity"]["question"]["prompt"]
    assert "criteria" not in json.dumps(opening["activity"])  # no answers leak to the client
    asyncio.run(supply_materials(agent_store, "alice", sid))

    activity = opening["activity"]
    kinds = ["question"]
    for turn in FIXTURE["turns"]:
        if turn["kind"] == "continue":
            r = client.post(f"{BASE}/{sid}/continue", json={"activity_id": activity["activity_id"]})
        else:
            q = activity["question"]
            body = {"question_id": q["question_id"], "shown": str(turn["value"])}
            body |= {"choice_id": turn["value"]} if turn["kind"] == "choice" else {"text": turn["value"]}
            r = client.post(f"{BASE}/{sid}/answers", json=body)
        assert r.status_code == 200, r.text
        messages = r.json()
        if turn["kind"] != "continue":
            assert messages[0]["role"] == "learner" and messages[0]["answer_for"] == activity["question"]["question_id"]
        activity = messages[-1]["activity"]
        kinds.append(activity["kind"])

    assert kinds[-1] == "completion"
    assert "explanation" in kinds  # it taught, not just quizzed
    stored = client.get(f"{BASE}/{sid}").json()["messages"]
    assert [m["role"] for m in stored].count("learner") == 3  # the 3 answers


def test_agent_failure_on_start_leaves_no_half_session():
    client, _, _ = make_client([DependencyError("model down", retryable=False)])
    r = client.post(BASE, json={"goal": "Bubble Sort"})
    assert r.status_code == 503 and "unavailable" in r.json()["detail"]
    assert client.get(BASE).json() == []


@pytest.mark.parametrize('mixed', [False, True])
def test_question_first_answers_preserve_sources_through_retry_restart_and_share(tmp_path, mixed):
    from types import SimpleNamespace
    from athena_api.sessions.store import SqliteSessionStore
    from athena_api.sessions.shared import SharedSessions
    parts = [{'text': 'Regression predicts numbers; classification predicts labels.', 'origin': 'materials'}]
    if mixed:
        parts.append({'text': 'House price prediction is a regression example.', 'origin': 'general'})
    check = {'supported': True, 'evidence': [{'source_index': 0, 'quote_index': 0}]}
    responses = [*FIXTURE['responses'][:4], {'intent': 'continue'}, {'parts': parts}, check]
    path = tmp_path / 'host.db'
    client, _, _ = make_client(responses, host_store=SqliteSessionStore(path))
    service = client.app.state.sessions
    opening = client.post(BASE, json={'goal': 'Bubble Sort'}).json()
    sid = opening['session']['id']
    queries = []
    source = dict(kind='document', source_id='slides-v1', passage_id='page-28', title='Prediction', page=28,
                  text='Regression predicts numbers.\nClassification predicts labels.')
    def retrieve(offering, query):
        queries.append(query)
        return [source]
    service.tutor.material = SimpleNamespace(for_goal=retrieve)
    url = f'{BASE}/{sid}/messages'
    question = 'What is the difference between regression and classification?'
    headers = {'Idempotency-Key': 'comparison'}
    response = client.post(url, json={'text': question}, headers=headers)
    assert response.status_code == 200, response.json()
    reply = response.json()[1]
    assert reply['knowledge_origin'] == ('supplement' if mixed else 'materials')
    assert reply['sources'][0]['page'] == 28 and reply['sources'][0]['quote'] == source['text']
    assert queries == [question]
    if mixed:
        assert '**General-knowledge addition:**' in reply['content']
    call_count = len(service.tutor.llm._llm.calls)
    service.store = SqliteSessionStore(path)  # Reload persisted messages and receipts.
    assert client.post(url, json={'text': question}, headers=headers).json() == response.json()
    assert len(service.tutor.llm._llm.calls) == call_count and queries == [question]
    stored = client.get(f'{BASE}/{sid}').json()['messages']
    assert next(m for m in stored if m['id'] == reply['id']) == reply
    assert len([m for m in stored if m['role'] == 'learner']) == 1
    service.share('alice', 'cse5alg-2026-s2', sid)
    token = service.store.get('alice', sid).share_token
    shared = SharedSessions(service.store).view('cse5alg-2026-s2', token)
    shared_reply = next(m for m in shared.messages if m.content == reply['content'])
    assert shared_reply.sources == reply['sources'] and shared_reply.knowledge_origin == reply['knowledge_origin']
    assert shared_reply.id != reply['id']


@pytest.mark.parametrize('kind', ['document', 'video'])
def test_grounded_start_with_multiline_material_preserves_citations_and_replays(kind):
    from types import SimpleNamespace
    text = 'Bubble Sort compares adjacent items.\r\nSwap when out of order.\t例子: "3, 1" → "1, 3".\n'
    source = dict(kind=kind, source_id='uploaded', title='Uploaded material')
    if kind == 'document':
        source.update(passage_id='page-4', text=text, page=4)
    else:
        source.update(segment_id='approved-clip', transcript=text, start_seconds=12.5, end_seconds=29.0)
    support = {'supported': True, 'evidence': [{'source_index': 0, 'quote_index': 0}]}
    responses = [item for generated in FIXTURE['responses'][:4] for item in (generated, support)]
    client, _, _ = make_client(responses)
    tutor = client.app.state.sessions.tutor
    tutor.material = SimpleNamespace(for_goal=lambda offering, goal: [source])
    headers = {'Idempotency-Key': 'multiline-start'}
    first = client.post(BASE, json={'goal': 'Bubble Sort'}, headers=headers)
    assert first.status_code == 201, first.json()
    opening = first.json()['messages'][0]
    citation = opening['sources'][0]
    assert citation['quote'] == text and citation['source_id'] == 'uploaded'
    assert opening['knowledge_origin'] == 'materials'
    if kind == 'document':
        assert citation['passage_id'] == 'page-4' and citation['page'] == 4
    else:
        assert citation['segment_id'] == 'approved-clip' and citation['start_seconds'] == 12.5
    assert len(tutor.llm._llm.calls) == 8
    replay = client.post(BASE, json={'goal': 'Bubble Sort'}, headers=headers)
    assert replay.json() == first.json()
    assert len(tutor.llm._llm.calls) == 8
    assert len(client.get(BASE).json()) == 1


def test_agent_sessions_are_per_student():
    client, _, who = make_client(FIXTURE["responses"])
    sid = client.post(BASE, json={"goal": FIXTURE["goal"]}).json()["session"]["id"]
    who["id"] = "bob"
    r = client.post(f"{BASE}/{sid}/answers", json={"question_id": "x", "choice_id": "b", "shown": "b"})
    assert r.status_code == 404


@pytest.mark.parametrize("body", [
    {"question_id": "q", "shown": "?"},
    {"question_id": "q", "choice_id": "a", "text": "both", "shown": "?"},
])
def test_answer_needs_exactly_one_of_choice_or_text(body):
    client, _, _ = make_client(FIXTURE["responses"])
    sid = client.post(BASE, json={"goal": FIXTURE["goal"]}).json()["session"]["id"]
    assert client.post(f"{BASE}/{sid}/answers", json=body).status_code == 422


def test_placeholder_tutor_rejects_answers():
    who = {"id": "alice"}
    client = TestClient(create_app(srs=SrsService(MemoryStore()), sessions=SessionService(MemorySessionStore(), tutor=PlaceholderTutor()),
                                   resolve_student=lambda _r: who["id"]))
    sid = client.post(BASE, json={"goal": "x"}).json()["session"]["id"]
    r = client.post(f"{BASE}/{sid}/answers", json={"question_id": "q", "choice_id": "a", "shown": "a"})
    assert r.status_code == 400


def test_scripted_demo_tutor_runs_a_whole_session(monkeypatch, tmp_path):
    from athena_api.sessions.agent_tutor import ScriptedDemoTutor, agent_tutor_from_env

    monkeypatch.setenv("ATHENA_TUTOR", "demo")
    tutor = agent_tutor_from_env()
    assert isinstance(tutor, ScriptedDemoTutor)
    client = TestClient(create_app(srs=SrsService(MemoryStore()), sessions=SessionService(MemorySessionStore(), tutor=tutor),
                                   resolve_student=lambda _r: "alice"))
    for _ in range(2):  # each session gets its own script
        created = client.post(BASE, json={"goal": "anything"}).json()
        sid, activity = created["session"]["id"], created["messages"][0]["activity"]
        for turn in FIXTURE["turns"]:
            if turn["kind"] == "continue":
                r = client.post(f"{BASE}/{sid}/continue", json={"activity_id": activity["activity_id"]})
            else:
                body = {"question_id": activity["question"]["question_id"], "shown": "x"}
                body |= {"choice_id": turn["value"]} if turn["kind"] == "choice" else {"text": turn["value"]}
                r = client.post(f"{BASE}/{sid}/answers", json=body)
            assert r.status_code == 200, r.text
            activity = r.json()[-1]["activity"]
        assert activity["kind"] == "completion"
