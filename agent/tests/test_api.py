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
