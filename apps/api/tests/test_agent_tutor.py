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


def make_client(responses):
    agent_store = InMemoryConversationStore()
    tutor = AgentTutor(agent_store, ReliableLLM(MockLLM(responses), policy=RetryPolicy(max_attempts=1)))
    who = {"id": "alice"}
    app = create_app(srs=SrsService(MemoryStore()), sessions=SessionService(MemorySessionStore(), tutor=tutor),
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
