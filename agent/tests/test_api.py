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
