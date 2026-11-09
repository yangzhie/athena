import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError
from pydantic import SecretStr, ValidationError

from athena_agent.learning import CompletionActivity
from athena_agent.llm import DependencyError, InvalidOutputError, Message, ModelRefusalError
from athena_agent.openai_llm import OpenAILLM, OpenAISettings


@pytest.fixture
def client():
    client = MagicMock()
    client.with_options.return_value = client
    client.responses.parse = AsyncMock(return_value=SimpleNamespace(
        output=[], status='completed',
        output_parsed=CompletionActivity(activity_id='a1', text='Ready'),
    ))
    client.close = AsyncMock()
    return client


def generate(client):
    adapter = OpenAILLM(OpenAISettings(model='test-model'), client=client)
    return asyncio.run(adapter.generate([Message(role='user', content='Teach')], CompletionActivity))


def test_adapter_sends_structured_request(client):
    assert generate(client).text == 'Ready'
    client.with_options.assert_called_once_with(max_retries=0, timeout=30.0)
    client.responses.parse.assert_awaited_once_with(
        model='test-model', input=[{'role': 'user', 'content': 'Teach'}],
        text_format=CompletionActivity, max_output_tokens=2048, store=False,
    )


def test_settings_load_from_environment_without_exposing_key(monkeypatch):
    monkeypatch.setenv('OPENAI_MODEL', 'configured-model')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-secret')
    settings = OpenAISettings.from_env()
    assert settings.model == 'configured-model'
    assert settings.api_key.get_secret_value() == 'test-secret'
    assert 'test-secret' not in repr(settings)
    assert 'api_key' not in settings.model_dump()


def test_missing_model_and_key_fail_explicitly(monkeypatch):
    monkeypatch.delenv('OPENAI_MODEL', raising=False)
    with pytest.raises(DependencyError, match='OPENAI_MODEL'):
        OpenAISettings.from_env()
    with pytest.raises(DependencyError, match='OPENAI_API_KEY'):
        OpenAILLM(OpenAISettings(model='test'))


@pytest.mark.parametrize('values', [
    {'model': ' '}, {'model': 'test', 'timeout': 0},
    {'model': 'test', 'timeout': float('inf')},
    {'model': 'test', 'max_output_tokens': 0},
])
def test_invalid_settings(values):
    with pytest.raises(ValidationError):
        OpenAISettings(**values)


@pytest.mark.parametrize('status,retryable', [(400, False), (401, False), (403, False), (408, True), (409, True), (429, True), (500, True)])
def test_status_errors_are_sanitized(client, status, retryable):
    response = httpx.Response(status, request=httpx.Request('POST', 'https://example.test'))
    client.responses.parse.side_effect = APIStatusError('private provider body', response=response, body={'secret': 'private'})
    with pytest.raises(DependencyError) as failure:
        generate(client)
    assert failure.value.retryable is retryable
    assert 'private' not in str(failure.value)
    assert failure.value.__suppress_context__


@pytest.mark.parametrize('error_type', [APIConnectionError, APITimeoutError])
def test_connection_failures_are_retryable(client, error_type):
    client.responses.parse.side_effect = error_type(request=httpx.Request('POST', 'https://example.test'))
    with pytest.raises(DependencyError) as failure:
        generate(client)
    assert failure.value.retryable


def test_refusal_is_terminal(client):
    client.responses.parse.return_value = SimpleNamespace(
        output=[SimpleNamespace(type='message', content=[SimpleNamespace(type='refusal')])],
        status='completed', output_parsed=None,
    )
    with pytest.raises(ModelRefusalError) as failure:
        generate(client)
    assert not failure.value.retryable


def test_incomplete_output_is_terminal(client):
    client.responses.parse.return_value.status = 'incomplete'
    with pytest.raises(DependencyError) as failure:
        generate(client)
    assert not failure.value.retryable


def test_missing_parsed_output_is_invalid(client):
    client.responses.parse.return_value.output_parsed = None
    with pytest.raises(InvalidOutputError):
        generate(client)


def test_owned_client_closed_and_injected_client_left_open(client):
    async def use_injected():
        async with OpenAILLM(OpenAISettings(model='test'), client=client):
            pass
    asyncio.run(use_injected())
    client.close.assert_not_awaited()
    with patch('athena_agent.openai_llm.AsyncOpenAI', return_value=client) as constructor:
        async def use_owned():
            async with OpenAILLM(OpenAISettings(model='test', api_key=SecretStr('test-key'))):
                pass
        asyncio.run(use_owned())
    constructor.assert_called_once_with(api_key='test-key', max_retries=0, timeout=30.0)
    client.close.assert_awaited_once()


def test_real_sdk_parsing_with_local_http_transport():
    import json
    from openai import AsyncOpenAI

    requests = []

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={
            'id': 'resp_test', 'object': 'response', 'created_at': 0,
            'model': 'test-model', 'status': 'completed',
            'output': [{
                'id': 'msg_test', 'type': 'message', 'role': 'assistant',
                'status': 'completed', 'content': [{
                    'type': 'output_text', 'annotations': [],
                    'text': '{"kind":"completion","activity_id":"a1","text":"Ready"}',
                }],
            }],
            'parallel_tool_calls': False, 'tool_choice': 'auto', 'tools': [],
        })

    async def run():
        async with AsyncOpenAI(
            api_key='test-only', http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
        ) as sdk:
            adapter = OpenAILLM(OpenAISettings(model='test-model'), client=sdk)
            return await adapter.generate([Message(role='user', content='Teach')], CompletionActivity)

    assert asyncio.run(run()).text == 'Ready'
    output_format = requests[0]['text']['format']
    assert output_format['type'] == 'json_schema'
    assert output_format['strict'] is True
    assert output_format['schema']['additionalProperties'] is False
    assert requests[0]['store'] is False
