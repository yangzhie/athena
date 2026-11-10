import asyncio
import copy
import json
import sqlite3
from types import SimpleNamespace

import pytest
from athena_agent.llm import MockLLM, DependencyError
from fastapi import HTTPException

from .test_playground_persistence import setup, SCENE, CODE, bundle


def live(service, responses):
    model = MockLLM(responses)
    service.sessions.tutor = SimpleNamespace(mode='ai', llm=model, material=None)
    return model


def ask(service, student, offering, session, operation, text='Build an experiment', kind='scene'):
    return asyncio.run(service.tutor.turn(student, offering, session, operation, text, kind))


def test_generated_scene_and_tool_outcomes_are_observed_before_publishing(tmp_path):
    client, service, student, offering, session, base = setup(tmp_path)
    model = live(service, [{'scene_json': json.dumps(SCENE), 'explanation': 'Explore forces'}, {'text': 'The force scene is open. Why might the force change sign?'}])
    result = ask(service, student, offering, session, 'generate-one')
    assert result['tool_results'][0] == {'ok': True, 'status': 'done'}
    assert 'tool_results' in model.calls[1].messages[-1].content
    assert 'current_snapshot' in model.calls[1].messages[-1].content
    assert client.get(base).json()['snapshot']['scene']['id'] == 'force'
    assert ask(service, student, offering, session, 'generate-one') == result
    assert len(model.calls) == 2
    messages = client.get(base.removesuffix('/playground')).json()['messages']
    assert messages[-1]['content'].startswith('General knowledge')
    assert messages[-2]['content'] == 'Build an experiment'
    with pytest.raises(HTTPException) as error:
        ask(service, student, offering, session, 'generate-one', text='different')
    assert error.value.status_code == 409


def test_two_repairs_then_text_fallback_no_invalid_scene(tmp_path):
    client, service, student, offering, session, base = setup(tmp_path)
    model = live(service, [{'scene_json': '{}', 'explanation': 'bad'}] * 3)
    result = ask(service, student, offering, session, 'repair-scene')
    assert len(model.calls) == 3
    assert 'after two repairs' in result['messages'][-1]['content']
    assert client.get(base).json()['checkpoint'] is None


def test_failed_tool_does_not_execute_or_claim_success(tmp_path):
    client, service, student, offering, session, base = setup(tmp_path)
    service.command(student, offering, session, 'open-force', 0, {'kind': 'open', 'scene': SCENE}, trusted=True)
    model = live(service, [{'explanation': 'Run invented tool', 'calls_json': '[{"name":"invented","input":{}}]'}, {'text': 'The requested tool was rejected. Let’s reason through it.'}])
    result = ask(service, student, offering, session, 'bad-tool', 'What happens?', 'question')
    assert not result['tool_results'][0]['ok']
    assert 'Unknown tool' in model.calls[-1].messages[-1].content
    assert client.get(base).json()['revision'] == 1


def test_model_result_survives_host_storage_failure_and_replay(tmp_path):
    client, service, student, offering, session, base = setup(tmp_path)
    model = live(service, [{'scene_json': json.dumps(SCENE), 'explanation': 'Explore forces'}, {'text': 'Scene is open. Explain the sign.'}])
    with service.db:
        service.db.execute("CREATE TRIGGER fail_playground_publish BEFORE INSERT ON session_messages BEGIN SELECT RAISE(ABORT, 'injected'); END")
    with pytest.raises(sqlite3.Error):
        ask(service, student, offering, session, 'recover-turn')
    assert len(model.calls) == 2
    with service.db:
        service.db.execute('DROP TRIGGER fail_playground_publish')
    result = ask(service, student, offering, session, 'recover-turn')
    assert len(model.calls) == 2
    assert result['messages'][-1]['content'].endswith('Explain the sign.')
    assert client.get(base).json()['revision'] == 1


def test_replacement_requires_student_decision_and_rejection_survives_refresh(tmp_path):
    client, service, student, offering, session, base = setup(tmp_path)
    service.command(student, offering, session, 'open-force', 0, {'kind': 'open', 'scene': SCENE}, trusted=True)
    service.command(student, offering, session, 'student-move', 1, {'kind': 'action', 'action': {'objectId': 'force', 'type': 'setDistance', 'distance': .2}})
    live(service, [{'scene_json': json.dumps(CODE), 'explanation': 'Try code'}, {'text': 'Please confirm before replacing your work.'}])
    result = ask(service, student, offering, session, 'replace-turn')
    assert result['tool_results'][0]['status'] == 'needs-confirmation'
    view = client.get(base).json()
    assert view['snapshot']['scene']['id'] == 'force'
    proposal = view['replacements'][0]['id']
    body = {'operation_id': 'reject-scene', 'catalog_version': '1.0.0', 'revision': 2, 'command': {}}
    assert client.post(f'{base}/replacements/{proposal}/reject', json=body).status_code == 200
    assert client.get(base).json()['replacements'] == []
    assert client.post(f'{base}/replacements/{proposal}/accept', json=body).status_code == 409
    assert client.get(base).json()['snapshot']['scene']['id'] == 'force'


def test_execution_interpretation_replays_and_does_not_inflate_mastery(tmp_path):
    client, service, student, offering, session, base = setup(tmp_path)
    service.command(student, offering, session, 'open-python', 0, {'kind': 'open', 'scene': CODE}, trusted=True)
    service.command(student, offering, session, 'run-python', 1, {'kind': 'action', 'action': {'objectId': 'code', 'type': 'run'}})
    job, _ = service.executions.claim()
    service.executions.finish(job, {'ok': True, 'provenance': 'real-run', 'stdout': '42\n', 'values': {}, 'trace': []})
    model = live(service, [{'explanation': 'Python printed 42. Explain why multiplication gives this result.', 'calls_json': '[]'}])
    first = client.post(f"{base}/executions/{job['id']}/interpret")
    assert first.status_code == 200, first.text
    assert client.post(f"{base}/executions/{job['id']}/interpret").json() == first.json()
    assert len(model.calls) == 1 and '42\\n' in model.calls[0].messages[1].content
    assert client.get(base).json()['executions'][0]['interpreted']
    assert service.db.execute('SELECT count(*) FROM learner_evidence').fetchone()[0] == 0
