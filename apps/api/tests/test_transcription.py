from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import APIConnectionError

from athena_api.sessions import transcription
from athena_api.operations import ModelAdmission
from .test_agent_tutor import make_client, FIXTURE, BASE


@pytest.fixture
def voice(monkeypatch):
    client, _, identity = make_client(FIXTURE['responses'][:4])
    sid = client.post(BASE, json={'goal': 'Bubble Sort'}).json()['session']['id']
    generate = AsyncMock(return_value=SimpleNamespace(text='  Compare neighbouring values.  '))
    class Provider:
        def __init__(self, **kwargs):
            assert kwargs['max_retries'] == 0
        async def __aenter__(self):
            return SimpleNamespace(audio=SimpleNamespace(transcriptions=SimpleNamespace(create=generate)))
        async def __aexit__(self, *args):
            pass
    monkeypatch.setattr(transcription, 'AsyncOpenAI', Provider)
    monkeypatch.setattr(transcription, 'MODELS', ModelAdmission())
    monkeypatch.setenv('OPENAI_API_KEY', 'test-only')
    return client, identity, f'{BASE}/{sid}/transcriptions', generate, sid


def test_dictation_is_private_not_persisted_or_submitted(voice):
    client, _, url, generate, sid = voice
    before = client.get(f'{BASE}/{sid}').json()
    result = client.post(url, content=b'\x1aE\xdf\xa3synthetic', headers={'Content-Type': 'audio/webm;codecs=opus'})
    assert result.status_code == 200 and result.json() == {'text': 'Compare neighbouring values.'}
    assert result.headers['cache-control'] == 'no-store'
    assert client.get(f'{BASE}/{sid}').json() == before
    assert generate.await_count == 1
    assert generate.call_args.kwargs['file'][0] == 'answer.webm'


@pytest.mark.parametrize('case', ['other_student', 'other_offering', 'missing_session'])
def test_voice_rejects_unauthorised_session_before_model_call(voice, case):
    client, identity, url, generate, _ = voice
    if case == 'other_student': identity['id'] = 'another-student'
    elif case == 'other_offering': url = url.replace('cse5alg-2026-s2', 'other')
    else: url = url.replace('/transcriptions', '-missing/transcriptions')
    assert client.post(url, content=b'\x1aE\xdf\xa3audio', headers={'Content-Type': 'audio/webm'}).status_code == 404
    generate.assert_not_awaited()


@pytest.mark.parametrize('audio,mime,status', [
    (b'', 'audio/webm', 422), (b'not audio', 'audio/webm', 415),
    (b'<html/>', 'text/html', 415), (b'\x1aE\xdf\xa3' + b'x' * (2 * 1024 * 1024), 'audio/webm', 413),
])
def test_audio_limits_before_provider(voice, audio, mime, status):
    client, _, url, generate, _ = voice
    assert client.post(url, content=audio, headers={'Content-Type': mime}).status_code == status
    generate.assert_not_awaited()


@pytest.mark.parametrize('text', ['', ' ' * 10, 'x' * 4001])
def test_empty_or_oversized_transcript_is_rejected(voice, text):
    client, _, url, generate, _ = voice
    generate.return_value = SimpleNamespace(text=text)
    assert client.post(url, content=b'\x1aE\xdf\xa3audio', headers={'Content-Type': 'audio/webm'}).status_code == 422


def test_provider_failure_is_safe_and_draft_can_be_typed(voice):
    client, _, url, generate, _ = voice
    generate.side_effect = APIConnectionError(message='PRIVATE PROVIDER DETAIL', request=httpx.Request('POST', 'https://example.test'))
    response = client.post(url, content=b'\x1aE\xdf\xa3audio', headers={'Content-Type': 'audio/webm'})
    assert response.status_code == 503 and 'type your answer' in response.json()['detail']
    assert 'PRIVATE' not in response.text and generate.await_count == 1


def test_deleted_session_does_not_receive_transcription(voice):
    client, _, url, generate, sid = voice
    async def finish(**kwargs):
        client.app.state.sessions.store.delete('alice', sid)
        return SimpleNamespace(text='Private draft')
    generate.side_effect = finish
    result = client.post(url, content=b'\x1aE\xdf\xa3audio', headers={'Content-Type': 'audio/webm'})
    assert result.status_code == 404 and 'Private draft' not in result.text
