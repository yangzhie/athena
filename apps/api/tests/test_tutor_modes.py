"""Configuration never selects offline content without an explicit mode."""

import pytest
from athena_agent.llm import MockLLM, DependencyError
from athena_agent.sqlite_memory import MemoryUnavailableError

from athena_api.app import create_app
from athena_api.lectures.service import LectureService
from athena_api.lectures.store import MemoryLectureStore
from athena_api.sessions.agent_tutor import AgentTutor, ScriptedDemoTutor, agent_tutor_from_env
from athena_api.sessions.service import SessionService
from athena_api.sessions.store import MemorySessionStore
from athena_api.sessions.tutor import PlaceholderTutor, UnavailableTutor
from athena_api.srs.service import SrsService
from athena_api.srs.store import MemoryStore
from .http_client import TestClient
from .test_answer_retries import BASE, FIXTURE


def client_for_tutor(tutor):
    return TestClient(create_app(
        sessions=SessionService(MemorySessionStore(), tutor=tutor), srs=SrsService(MemoryStore()),
        lectures=LectureService(MemoryLectureStore()), resolve_student=lambda _r: "alice"))


@pytest.mark.parametrize("mode", [None, "ai", "typo"])
def test_unconfigured_tutor_is_unavailable_not_a_fixture(monkeypatch, mode):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    if mode:
        monkeypatch.setenv("ATHENA_TUTOR", mode)
    else:
        monkeypatch.delenv("ATHENA_TUTOR", raising=False)
    tutor = agent_tutor_from_env()
    assert isinstance(tutor, UnavailableTutor)
    client = client_for_tutor(tutor)
    assert client.get('/tutor/status').json() == {"mode": "unavailable", "available": False, "scripted": False}
    response = client.post(BASE, json={"goal": "Goal"})
    assert response.status_code == 503 and "unavailable" in response.json()["detail"]
    assert client.get(BASE).json() == []


@pytest.mark.parametrize("mode,kind,label", [("demo", ScriptedDemoTutor, "Scripted demo"), ("placeholder", PlaceholderTutor, "Placeholder tutor")])
def test_explicit_offline_modes_are_labelled(monkeypatch, mode, kind, label):
    monkeypatch.setenv("ATHENA_TUTOR", mode)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    tutor = agent_tutor_from_env()
    assert isinstance(tutor, kind)
    client = client_for_tutor(tutor)
    assert client.get('/tutor/status').json() == {"mode": mode, "available": True, "scripted": True}
    response = client.post(BASE, json={"goal": "Goal"})
    assert response.status_code == 201 and label in response.json()["messages"][0]["content"]


def test_configured_ai_uses_real_mode_and_storage_failure_is_unavailable(monkeypatch, tmp_path):
    import athena_agent.openai_llm as provider
    import athena_agent.sqlite_memory as storage
    monkeypatch.setenv("ATHENA_TUTOR", "ai")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("ATHENA_AGENT_DB", str(tmp_path / "agent.db"))
    # No SDK connection or paid call: only the explicitly injected offline model runs.
    monkeypatch.setattr(provider, "OpenAILLM", lambda _settings: MockLLM(FIXTURE["responses"]))
    tutor = agent_tutor_from_env()
    assert isinstance(tutor, AgentTutor) and not isinstance(tutor, ScriptedDemoTutor)
    client = client_for_tutor(tutor)
    assert client.get('/tutor/status').json() == {"mode": "ai", "available": True, "scripted": False}
    assert client.post(BASE, json={"goal": FIXTURE["goal"]}).status_code == 201
    tutor.store.close()

    def fail(*_args):
        raise MemoryUnavailableError()
    monkeypatch.setattr(storage, "SQLiteLearningMemory", fail)
    assert isinstance(agent_tutor_from_env(), UnavailableTutor)


def test_provider_failure_never_substitutes_scripted_content(tmp_path):
    from athena_agent.sqlite_memory import SQLiteLearningMemory
    with SQLiteLearningMemory(tmp_path / "agent.db") as store:
        client = client_for_tutor(AgentTutor(store, MockLLM([DependencyError("provider down", retryable=False)])))
        response = client.post(BASE, json={"goal": "Goal"})
        assert response.status_code == 503
        assert "placeholder" not in response.text and "provider down" not in response.text
        assert client.get(BASE).json() == []


def test_missing_demo_fixture_reports_unavailable(monkeypatch):
    import athena_api.sessions.agent_tutor as module
    monkeypatch.setenv("ATHENA_TUTOR", "demo")
    def missing(_path):
        raise FileNotFoundError("fixture missing")
    monkeypatch.setattr(module, "ScriptedDemoTutor", missing)
    assert isinstance(module.agent_tutor_from_env(), UnavailableTutor)
