import asyncio

import httpx

from athena_agent.api import create_app, create_demo_app
from athena_agent._schema import Contract, NonBlankString
from athena_agent.conversation import InMemoryConversationStore
from athena_agent.llm import MockLLM


def request(app, method, path, **kwargs):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            return await client.request(method, path, **kwargs)
    return asyncio.run(run())


def test_service_health_and_request_correlation():
    app = create_demo_app()
    response = request(app, 'GET', '/health', headers={'x-request-id': 'host-request'})
    assert response.status_code == 200
    assert response.json() == {'status': 'success', 'request_id': 'host-request', 'session_id': None, 'data': {'service': 'athena-agent', 'ready': True}}
    assert request(app, 'GET', '/health', headers={'x-request-id': ' '}).status_code == 422


def test_validation_errors_use_safe_envelopes_not_raw_payloads():
    app = create_app(InMemoryConversationStore(), MockLLM([]))
    class Probe(Contract):
        text: NonBlankString
    @app.post('/probe')
    async def probe(payload: Probe):
        return payload
    response = request(app, 'POST', '/probe', json={'text': 'private', 'extra': 'secret-value'})
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'invalid_request'
    assert 'secret-value' not in response.text
    assert response.json()['request_id']


def test_start_resume_use_host_identity_and_hide_private_records():
    from .test_orchestrator import one_concept_responses
    store = InMemoryConversationStore()
    mock = MockLLM(one_concept_responses())
    app = create_app(store, mock, learner_resolver=lambda request: app.state.trusted_learner)
    app.state.trusted_learner = 'host-learner'
    response = request(app, 'POST', '/sessions', json={'session_id': 's', 'goal': 'Comparisons'})
    assert response.status_code == 200, response.text
    assert response.json()['data']['kind'] == 'question'
    assert response.json()['session_id'] == 's'
    assert 'correct_choice_id' not in response.text and 'criteria' not in response.text
    resumed = request(app, 'GET', '/sessions/s/resume')
    assert resumed.json()['data'] == response.json()['data'] and len(mock.calls) == 4
    app.state.trusted_learner = 'other'
    foreign = request(app, 'GET', '/sessions/s/resume')
    assert foreign.status_code == 404 and foreign.json()['error']['code'] == 'session_not_found'


def test_start_rejects_client_identity_and_missing_host_without_model_calls():
    mock = MockLLM([])
    app = create_app(InMemoryConversationStore(), mock)
    assert request(app, 'POST', '/sessions', json={'session_id': 's', 'goal': 'Sorting'}).status_code == 400
    bound = create_app(InMemoryConversationStore(), mock, learner_resolver=lambda request: 'trusted')
    response = request(bound, 'POST', '/sessions', json={'session_id': 's', 'goal': 'Sorting', 'learner_id': 'forged'})
    assert response.status_code == 422 and mock.calls == []


def test_api_answers_teach_continue_and_preserve_idempotency():
    from .test_orchestrator import one_concept_responses, OPEN
    mock = MockLLM([*one_concept_responses(), {'misconceptions': [], 'prerequisite_gaps': []}, {'text': 'Compare adjacent values.'}, OPEN])
    app = create_app(InMemoryConversationStore(), mock, learner_resolver=lambda request: 'trusted')
    first = request(app, 'POST', '/sessions', json={'session_id': 's', 'goal': 'Sorting'}).json()['data']
    payload = {'answer': {'kind': 'multiple_choice', 'question_id': first['question']['question_id'], 'selected_choice_id': 'b'}}
    teaching = request(app, 'POST', '/sessions/s/answers', json=payload)
    assert teaching.status_code == 200 and teaching.json()['data']['kind'] == 'explanation'
    replay = request(app, 'POST', '/sessions/s/answers', json=payload)
    assert replay.json()['data'] == teaching.json()['data']
    followup = request(app, 'POST', '/sessions/s/continue', json={'activity_id': teaching.json()['data']['activity_id']})
    assert followup.status_code == 200 and followup.json()['data']['question']['kind'] == 'open_ended'
    malformed = request(app, 'POST', '/sessions/s/answers', json={'answer': {'kind': 'text', 'question_id': 'q', 'text': ' '}})
    assert malformed.status_code == 422


def test_message_clarification_preserves_current_question_and_topic_switch_replans():
    from .test_orchestrator import one_concept_responses
    mock = MockLLM([*one_concept_responses(), {'intent': 'clarification'}, {'text': 'Compare neighbours.'}, {'intent': 'topic_change', 'new_goal': 'Graphs'}, {'text': 'We will explore graphs.'}, *one_concept_responses()])
    store = InMemoryConversationStore()
    app = create_app(store, mock, learner_resolver=lambda request: 'trusted')
    first = request(app, 'POST', '/sessions', json={'session_id': 's', 'goal': 'Sorting'}).json()['data']
    clarification = request(app, 'POST', '/sessions/s/messages', json={'text': 'Explain that.'})
    assert clarification.status_code == 200 and clarification.json()['data']['activity'] == first
    assert first['question']['prompt'] in mock.calls[5].messages[1].content
    changed = request(app, 'POST', '/sessions/s/messages', json={'text': 'Switch to graphs.'})
    assert changed.status_code == 200 and changed.json()['data']['activity']['kind'] == 'question'
    from athena_agent.contracts import RequestContext
    session = store.read(RequestContext(request_id='check', learner_id='trusted', session_id='s'))
    assert session.active_topic.learning_state.goal == 'Graphs' and len(session.archived_topics) == 1
    assert session.active_topic.learning_state.mastery == []


def test_session_view_returns_consistent_public_state_progress_and_feedback():
    from .test_orchestrator import one_concept_responses
    from athena_agent.contracts import RequestContext
    mock = MockLLM([*one_concept_responses(), {'misconceptions': [], 'prerequisite_gaps': []}, {'text': 'Compare neighbours.'}])
    store = InMemoryConversationStore()
    app = create_app(store, mock, learner_resolver=lambda request: 'trusted')
    first = request(app, 'POST', '/sessions', json={'session_id': 's', 'goal': 'Sorting'}).json()['data']
    initial = request(app, 'GET', '/sessions/s').json()['data']
    assert initial['activity'] == first and initial['progress']['next_step'] == 'answer'
    assert initial['latest_feedback'] is None
    request(app, 'POST', '/sessions/s/answers', json={'answer': {'kind': 'multiple_choice', 'question_id': first['question']['question_id'], 'selected_choice_id': 'b'}})
    context = RequestContext(request_id='check', learner_id='trusted', session_id='s')
    before = store.read(context)
    response = request(app, 'GET', '/sessions/s')
    data = response.json()['data']
    assert data['activity']['kind'] == 'explanation' and data['learning_state']['phase'] == 'teach'
    assert data['progress']['next_step'] == 'continue'
    assert data['latest_feedback']['content']['outcome'] == 'incorrect'
    assert store.read(context) == before
    assert 'question_records' not in response.text and 'correct_choice_id' not in response.text
