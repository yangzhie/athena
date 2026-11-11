import asyncio
import json
import sqlite3
import time
from datetime import timedelta

import pytest
from athena_agent.contracts import RequestContext
from athena_agent.conversation import InMemoryConversationStore, SessionNotFoundError
from athena_agent.sqlite_memory import SQLiteLearningMemory

from .test_playground_persistence import setup, CODE, bundle
from .test_learning_memory import browser as learning_browser, journey
from .test_study_spaces import BODY


def test_deletion_removes_host_agent_playground_and_revokes_share(tmp_path):
    client, service, student, offering, session, base = setup(tmp_path)
    context = RequestContext(request_id='test', learner_id=student, session_id=session)
    # Exercise a separate durable agent database, including persisted receipts.
    agent = SQLiteLearningMemory(tmp_path / 'agent.db')
    agent.create(context)
    service.sessions.tutor.store = agent
    service.command(student, offering, session, 'open-python', 0, {'kind': 'open', 'scene': CODE}, trusted=True)
    service.command(student, offering, session, 'run-python', 1, {'kind': 'action', 'action': {'objectId': 'code', 'type': 'run'}})
    job, _ = service.executions.claim()
    client.post(base.removesuffix('/playground') + '/share')
    shared = client.get(f'/units/{offering}/shared-sessions').json()[0]['share_id']
    assert client.delete(base.removesuffix('/playground')).status_code == 204
    assert client.delete(base.removesuffix('/playground')).status_code == 204
    assert client.get(base).status_code == 404
    assert client.get(f'/units/{offering}/shared-sessions/{shared}').status_code == 404
    with pytest.raises(SessionNotFoundError):
        agent.read(context)
    for table, column in [('session_messages', 'session_id'), ('session_operations', 'session_id'), ('playgrounds', 'session'), ('playground_operations', 'session'), ('playground_events', 'session'), ('executions', 'session')]:
        assert service.db.execute(f'SELECT count(*) FROM {table} WHERE {column}=?', (session,)).fetchone()[0] == 0
    assert service.db.execute('SELECT container FROM execution_cleanup').fetchone()[0] == job['container']
    # A worker that finishes late cannot recreate deleted private execution output.
    service.executions.finish(job, {'ok': True})
    assert service.executions.list(student, session) == []


def test_failed_agent_cleanup_is_hidden_revoked_and_resumes(tmp_path):
    client, service, student, offering, session, base = setup(tmp_path)
    agent = service.sessions.tutor.store
    original = agent.delete
    def fail(_):
        raise OSError('injected')
    agent.delete = fail
    client.post(base.removesuffix('/playground') + '/share')
    shared = client.get(f'/units/{offering}/shared-sessions').json()[0]['share_id']
    assert client.delete(base.removesuffix('/playground')).status_code == 503
    assert client.get(base.removesuffix('/playground')).status_code == 404
    assert client.get(f'/units/{offering}/shared-sessions/{shared}').status_code == 404
    agent.delete = original
    lifecycle = client.app.state.lifecycle
    assert lifecycle.sweep() == 1
    assert not lifecycle.unavailable(session)
    assert client.get(base).status_code == 404


def test_retention_expires_conversations_and_preserves_shared_material(tmp_path, monkeypatch):
    client, service, student, offering, session, base = setup(tmp_path)
    stored = service.sessions.store.get(student, session)
    old = stored.model_copy(update={'created_at': stored.created_at - timedelta(days=31)})
    service.sessions.store.put(old)
    assert client.app.state.lifecycle.sweep() == 1
    assert client.get(base).status_code == 404
    assert client.get(f'/offerings/{offering}').status_code == 200
    assert client.get(f'/units/{offering}/materials').status_code == 200
    assert client.app.state.lifecycle.sweep() == 0
    monkeypatch.setenv('ATHENA_PRIVATE_RETENTION_DAYS', '0')
    with pytest.raises(ValueError):
        client.app.state.lifecycle.sweep()


def test_deleting_evidence_updates_private_profile_and_practice(tmp_path):
    client, spaces, memory, tutor, srs, _ = learning_browser(tmp_path)
    offering = client.post('/offerings', json=BODY).json()['id']
    client.post(f'/offerings/{offering}/publish')
    from athena_api.srs.models import Bank
    srs.store.put_bank(Bank(offering_id=offering, items=[]))
    student, session = journey(client, spaces, tutor, offering)
    assert client.get('/learner/profile').json()[0]['status'] == 'mastered'
    assert client.get(f'/units/{offering}/srs/next').json()['done'] is False
    assert client.delete(f'/units/{offering}/sessions/{session}').status_code == 204
    assert client.get('/learner/profile').json() == []
    assert client.get(f'/units/{offering}/srs/next').json()['done'] is True
    assert client.get(f'/units/{offering}/progress/evidence').json() == []


def test_expiry_cleans_agent_state_when_ai_credentials_are_unavailable(tmp_path):
    client, service, student, offering, session, base = setup(tmp_path)
    from athena_api.sessions.tutor import UnavailableTutor
    service.sessions.tutor = UnavailableTutor('No key')
    agent = SQLiteLearningMemory(tmp_path / 'agent.db')
    context = RequestContext(request_id='test', learner_id=student, session_id=session)
    agent.create(context)
    assert client.delete(base.removesuffix('/playground')).status_code == 204
    with pytest.raises(SessionNotFoundError):
        agent.read(context)
