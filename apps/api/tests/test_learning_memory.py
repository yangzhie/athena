"""Canonical evidence, private Practice and suppression across browser identities."""
import asyncio
import json
from pathlib import Path

from athena_agent.conversation import InMemoryConversationStore
from athena_agent.contracts import RequestContext
from athena_agent.knowledge import KnowledgeService
from athena_agent.llm import MockLLM
from athena_agent.memory import LearnerScopedMemory
from athena_agent.reliable_llm import ReliableLLM, RetryPolicy
from athena_agent.retrieval import RetrievalResult
from athena_api.app import create_app
from athena_api.lectures.service import LectureService
from athena_api.lectures.store import SqliteLectureStore
from athena_api.sessions.agent_tutor import AgentTutor
from athena_api.sessions.service import SessionService
from athena_api.sessions.store import SqliteSessionStore
from athena_api.spaces.service import StudySpaces
from athena_api.srs.models import Bank
from athena_api.srs.service import SrsService
from athena_api.srs.store import SqliteStore
from .http_client import TestClient
from .test_study_spaces import BODY

FIXTURE = json.loads((Path(__file__).parents[3] / 'agent/tests/fixtures/api_journey.json').read_text())


def browser(tmp_path):
    path = tmp_path / 'host.db'
    spaces = StudySpaces(path)
    llm = MockLLM(FIXTURE['responses'])
    tutor = AgentTutor(InMemoryConversationStore(), ReliableLLM(llm, policy=RetryPolicy(max_attempts=1)))
    srs = SrsService(SqliteStore(path))
    app = create_app(spaces=spaces, srs=srs, sessions=SessionService(SqliteSessionStore(path), tutor=tutor),
                     lectures=LectureService(SqliteLectureStore(path)))
    tutor.material = None  # Explicit test-only fixture supply, not normal retrieval.
    return TestClient(app), spaces, app.state.learning, tutor, srs, llm


def journey(client, spaces, tutor, offering, retry=False):
    base = f'/units/{offering}/sessions'
    response = client.post(base, json={'goal': FIXTURE['goal']})
    assert response.status_code == 201, response.text
    created = response.json()
    student, _ = spaces.identity(client.cookies.get('athena_session'))
    session = created['session']['id']
    context = RequestContext(request_id='fixture', learner_id=student, session_id=session)
    asyncio.run(KnowledgeService(LearnerScopedMemory(tutor.store, student)).supply(context, RetrievalResult.model_validate(FIXTURE['materials'])))
    activity = created['messages'][0]['activity']
    for turn in FIXTURE['turns']:
        if turn['kind'] == 'continue':
            response = client.post(f'{base}/{session}/continue', json={'activity_id': activity['activity_id']})
        else:
            body = dict(question_id=activity['question']['question_id'], shown='Private learner response')
            body.update({'choice_id': turn['value']} if turn['kind'] == 'choice' else {'text': turn['value']})
            response = client.post(f'{base}/{session}/answers', json=body)
            if retry:
                replay = client.post(f'{base}/{session}/answers', json=body)
                assert replay.status_code == response.status_code and replay.json() == response.json()
        assert response.status_code == 200, response.text
        activity = response.json()[-1]['activity']
    assert activity['kind'] == 'completion'
    return student, session


def test_profile_practice_and_source_evidence_survive_retries_and_new_sessions(tmp_path):
    client, spaces, memory, tutor, srs, _ = browser(tmp_path)
    offering = client.post('/offerings', json=BODY).json()['id']
    client.post(f'/offerings/{offering}/publish')
    srs.store.put_bank(Bank(offering_id=offering, items=[]))
    student, session = journey(client, spaces, tutor, offering, retry=True)
    profile = client.get('/learner/profile').json()
    assert len(profile) == 1 and profile[0]['id'] == 'bubble-sort'
    assert profile[0]['status'] == 'mastered' and profile[0]['evidence_count'] == 3
    assert len(client.get(f'/units/{offering}/progress/evidence').json()) == 3
    practice = client.get(f'/units/{offering}/srs/next').json()
    assert not practice['done'] and practice['item_id'].startswith('private:')
    assert 'rubric' not in practice['question'] and 'answer_index' not in practice['question']
    assert client.get(f'/units/{offering}/srs/bank').json() == {'offering_id': offering, 'items': []}
    other, _, _, _, _, _ = browser(tmp_path)
    assert other.get('/learner/profile').json() == []
    assert other.get(f'/units/{offering}/srs/next').json()['done']
    assert other.get(f'/units/{offering}/progress/evidence').json() == []
    fresh, fresh_spaces, _, fresh_tutor, _, llm = browser(tmp_path)
    fresh.cookies.update(client.cookies)
    created = fresh.post(f'/units/{offering}/sessions', json={'goal': FIXTURE['goal']})
    assert created.status_code == 201
    assert created.json()['session']['id'] != session and len(created.json()['messages']) == 1
    assert any('Student-owned prior Concept knowledge' in message.content for message in llm.calls[0].messages)
    fresh_profile = fresh.get('/learner/profile').json()[0]
    assert fresh_profile['evidence_count'] == 3 and fresh_profile['status'] == 'mastered'


def test_lecturer_aggregates_require_five_environments_and_never_include_private_data(tmp_path):
    owner, spaces, memory, tutor, _, _ = browser(tmp_path)
    offering = owner.post('/offerings', json=BODY).json()['id']
    owner.post(f'/offerings/{offering}/publish')
    learner, session = journey(owner, spaces, tutor, offering)
    for _ in range(4):
        assert not owner.get(f'/units/{offering}/insights').json()['sufficient_data']
        client, other_spaces, _, other_tutor, _, _ = browser(tmp_path)
        journey(client, other_spaces, other_tutor, offering)
    response = owner.get(f'/units/{offering}/insights')
    result = response.json()
    assert result['sufficient_data'] and result['contributing_environments'] == 5
    assert result['sessions'] == 5 and result['completed_sessions'] == 5
    assert result['concepts'][0]['id'] == 'bubble-sort'
    assert result['concepts'][0]['assessments'] == 15
    for forbidden in [learner, session, 'Private learner response', 'criteria', 'rubric', 'note', 'student_id']:
        assert forbidden not in response.text
    assert client.get(f'/units/{offering}/insights').status_code == 403
    unrelated = owner.post('/offerings', json={**BODY, 'code': 'OTHER', 'title': 'Other Unit'}).json()['id']
    owner.post(f'/offerings/{unrelated}/publish')
    assert owner.get(f'/units/{unrelated}/insights').json()['concepts'] == []


def test_generated_ids_are_not_canonical_and_ambiguous_concepts_do_not_leak(tmp_path):
    client, spaces, memory, tutor, _, _ = browser(tmp_path)
    offering = client.post('/offerings', json=BODY).json()['id']
    client.post(f'/offerings/{offering}/publish')
    with memory.lock, memory.db:
        assert memory.canonical(offering, 'Bubble Sort') == memory.canonical('other-offering', 'bubble-sort') == 'bubble-sort'
        first = memory.canonical(offering, 'Normalization', 'Feature scaling')
        second = memory.canonical(offering, 'Normalization', 'Relational database design')
        assert first != second and first != memory.canonical('other', 'Normalization', 'Feature scaling')
    topic = client.post(f'/units/{offering}/topics', json={'title': 'Normalization'}).json()
    with memory.lock, memory.db:
        assert memory.canonical(offering, 'Normalization', 'A fresh description') == topic['concept_id']
    assert topic['concept_id'].startswith('course:')
    assert client.post(f'/units/{offering}/topics', json={'title': 'Wrong', 'concept_id': first}).status_code == 422


def test_replay_repairs_projection_after_host_commit_without_duplicate_evidence(tmp_path):
    client, spaces, memory, tutor, _, _ = browser(tmp_path)
    offering = client.post('/offerings', json=BODY).json()['id']
    client.post(f'/offerings/{offering}/publish')
    original = memory.sync
    fail_once = [True]
    def flaky(operation):
        if operation.kind == 'answer' and fail_once[0]:
            fail_once[0] = False
            import sqlite3
            raise sqlite3.OperationalError('injected projection failure')
        return original(operation)
    # Exercise answer replay through the actual SessionService and HTTP error mapping.
    service = client.app.state.sessions
    service.evidence_sink = flaky
    created = client.post(f'/units/{offering}/sessions', json={'goal': FIXTURE['goal']}).json()
    student, _ = spaces.identity(client.cookies.get('athena_session'))
    context = RequestContext(request_id='fixture', learner_id=student, session_id=created['session']['id'])
    asyncio.run(KnowledgeService(LearnerScopedMemory(tutor.store, student)).supply(context, RetrievalResult.model_validate(FIXTURE['materials'])))
    question = created['messages'][0]['activity']['question']['question_id']
    url = f"/units/{offering}/sessions/{created['session']['id']}/answers"
    body = {'question_id': question, 'choice_id': 'b', 'shown': 'Private response'}
    assert client.post(url, json=body).status_code == 503
    assert client.post(url, json=body).status_code == 200
    assert client.post(url, json=body).status_code == 200
    assert len(client.get(f'/units/{offering}/progress/evidence').json()) == 1
