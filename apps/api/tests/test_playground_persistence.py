"""Use the real TS engine: no Python reimplementation or mocked validation."""
import json
import subprocess
from pathlib import Path

import pytest
from fastapi import HTTPException

from athena_api.playground.bridge import BUNDLE, catalog, transition
from athena_api.app import create_app
from athena_api.sessions.agent_tutor import ScriptedDemoTutor
from athena_api.sessions.service import SessionService
from athena_api.sessions.store import SqliteSessionStore
from athena_api.srs.service import SrsService
from athena_api.srs.store import SqliteStore
from athena_api.lectures.service import LectureService
from athena_api.lectures.store import SqliteLectureStore
from athena_api.spaces.service import StudySpaces
from .http_client import TestClient
from .test_study_spaces import BODY

SCENE = {
    'id': 'force', 'title': 'Attraction', 'goal': 'Find a balanced distance',
    'objects': [{'id': 'force', 'type': 'force-lab', 'title': 'Two particles', 'provenance': 'ai-estimate',
                 'config': {'particles': [{'label': 'A', 'color': '#abc', 'radius': .1}, {'label': 'B', 'color': '#abc', 'radius': .1}],
                            'curve': [{'r': .1, 'f': 10}, {'r': .2, 'f': 0}, {'r': .3, 'f': -5}, {'r': .5, 'f': 0}],
                            'forceUnit': 'N', 'range': [.1, .5], 'initialDistance': .3}}],
    'checks': [{'id': 'balanced', 'objectId': 'force', 'on': ['setDistance'],
                'when': {'field': 'regime', 'op': 'eq', 'value': 'balanced'}, 'verdict': 'correct',
                'explain': 'Now explain why.', 'completesGoal': True}],
}
CODE = {'id': 'python', 'title': 'Python', 'goal': 'Predict the output',
        'objects': [{'id': 'code', 'type': 'code-graph', 'title': 'Python', 'provenance': 'concept',
                     'config': {'language': 'python', 'source': 'print(6 * 7)', 'probeValues': ['0']}}],
        'checks': [{'id': 'ran', 'objectId': 'code', 'on': ['runCompleted'],
                    'when': {'field': 'ok', 'op': 'eq', 'value': True}, 'verdict': 'correct',
                    'explain': 'Output verified; explain it independently.', 'completesGoal': True}]}


@pytest.fixture(scope='module', autouse=True)
def bundle():
    subprocess.run(['npm', 'run', 'build:headless', '-w', '@athena/playground'], cwd=Path(__file__).parents[3], check=True, capture_output=True)
    catalog.cache_clear()
    assert BUNDLE.exists()


def browser(path, lecturer=False):
    spaces = StudySpaces(path)
    sessions = SessionService(SqliteSessionStore(path), tutor=ScriptedDemoTutor(Path(__file__).parents[3] / 'agent/tests/fixtures/api_journey.json'))
    app = create_app(spaces=spaces, sessions=sessions, srs=SrsService(SqliteStore(path)),
                     lectures=LectureService(SqliteLectureStore(path)))
    client = TestClient(app)
    if lecturer:
        from .lecturer_access import make_lecturer
        make_lecturer(client)
    return client, app.state.playgrounds


def setup(tmp_path):
    client, service = browser(tmp_path / 'host.db', lecturer=True)
    offering = client.post('/offerings', json=BODY).json()['id']
    client.post(f'/offerings/{offering}/publish')
    session = client.post(f'/units/{offering}/sessions', json={'goal': 'Forces'}).json()['session']['id']
    base = f'/units/{offering}/sessions/{session}/playground'
    student, _ = service.spaces.identity(client.cookies.get('athena_session'))
    return client, service, student, offering, session, base


def command(client, base, op, revision, cmd):
    return client.post(base + '/commands', json={'operation_id': op, 'revision': revision, 'catalog_version': '1.0.0', 'command': cmd})


def test_scene_actions_replay_conflict_restart_and_ownership(tmp_path):
    client, service, student, offering, session, base = setup(tmp_path)
    assert client.get(base).json()['revision'] == 0
    opened = service.command(student, offering, session, 'open-scene', 0, {'kind': 'open', 'scene': SCENE}, trusted=True)
    assert opened['revision'] == 1
    action = {'kind': 'action', 'action': {'objectId': 'force', 'type': 'setDistance', 'distance': .2}}
    first = command(client, base, 'move-once', 1, action)
    assert first.status_code == 200, first.text
    assert command(client, base, 'move-once', 1, action).json() == first.json()
    assert command(client, base, 'move-twice', 1, action).status_code == 409
    changed = json.loads(json.dumps(action)); changed['action']['distance'] = .3
    assert command(client, base, 'move-once', 1, changed).status_code == 409
    fresh, other_service = browser(tmp_path / 'host.db')
    assert fresh.get(base).status_code == 404
    fresh.cookies.update(client.cookies)
    restored = fresh.get(base).json()
    assert restored['revision'] == 2
    assert restored['snapshot']['objects'][0]['state']['distance_nm'] == .2
    other = client.post('/offerings', json={**BODY, 'code': 'OTHER'}).json()['id']
    client.post(f'/offerings/{other}/publish')
    assert client.get(base.replace(offering, other)).status_code == 404
    assert command(client, base, 'bad-system', 2, {'kind': 'execution', 'result': {}}).status_code == 422
    assert command(client, base, 'bad-action', 2, {'kind': 'action', 'action': {'objectId': 'force', 'type': 'runCompleted'}}).status_code == 422
    assert command(client, base, 'bad-shape', 2, {'kind': 'action', 'action': {'objectId': 'force', 'type': 'setDistance', 'distance': 'bad'}}).status_code == 422


def test_tools_validate_configs_and_require_proposal_before_discarding_work(tmp_path):
    client, service, student, offering, session, base = setup(tmp_path)
    service.command(student, offering, session, 'open-scene', 0, {'kind': 'open', 'scene': SCENE}, trusted=True)
    command(client, base, 'move-once', 1, {'kind': 'action', 'action': {'objectId': 'force', 'type': 'setDistance', 'distance': .2}})
    with pytest.raises(HTTPException) as error:
        service.command(student, offering, session, 'bad-update', 2, {'kind': 'tool', 'call': {'name': 'update_config', 'input': {'objectId': 'force', 'config': {'range': 'bad'}, 'reason': 'test'}}}, trusted=True)
    assert error.value.status_code == 422
    proposed = service.command(student, offering, session, 'update-config', 2, {'kind': 'tool', 'call': {'name': 'update_config', 'input': {'objectId': 'force', 'config': {'initialDistance': .4}, 'reason': 'Try a different distance'}}}, trusted=True)
    assert proposed['result']['status'] == 'needs-confirmation'
    proposal = proposed['result']['proposalId']
    rejected = command(client, base, 'reject-change', 3, {'kind': 'reject', 'proposal_id': proposal})
    assert rejected.json()['snapshot']['objects'][0]['state']['distance_nm'] == .2
    with pytest.raises(HTTPException) as error:
        service.command(student, offering, session, 'replace-scene', 4, {'kind': 'open', 'scene': SCENE}, trusted=True)
    assert error.value.status_code == 422


def test_execution_is_enqueued_atomically_and_only_worker_result_applies(tmp_path):
    client, service, student, offering, session, base = setup(tmp_path)
    service.command(student, offering, session, 'open-python', 0, {'kind': 'open', 'scene': CODE}, trusted=True)
    action = {'kind': 'action', 'action': {'objectId': 'code', 'type': 'run'}}
    first = command(client, base, 'run-python', 1, action)
    assert first.status_code == 200, first.text
    assert command(client, base, 'run-python', 1, action).json() == first.json()
    jobs = client.get(base + '/executions').json()
    assert len(jobs) == 1 and jobs[0]['state'] == 'queued'
    assert jobs[0]['source'] == 'print(6 * 7)' and 'student' not in jobs[0] and 'token' not in jobs[0]
    job, _ = service.executions.claim()
    result = {'ok': True, 'provenance': 'real-run', 'stdout': '42\n', 'values': {}, 'trace': []}
    service.executions.finish(job, result)
    restored = client.get(base).json()
    assert restored['revision'] == 3
    assert restored['snapshot']['objects'][0]['state']['lastRun']['provenance'] == 'real-run'
    assert client.get(base).json()['revision'] == 3
    assert service.db.execute('SELECT count(*) FROM aggregate_events').fetchone()[0] == 0
    assert service.db.execute('SELECT count(*) FROM learner_evidence').fetchone()[0] == 0


def test_contract_and_malformed_scenes_are_explicit():
    data = catalog()
    assert data['catalog_version'] == '1.0.0' and not data['capabilities']['traces']
    assert len(data['components']) == 19 and len(data['tools']) == 8
    with pytest.raises(HTTPException) as error:
        transition(None, {'kind': 'open', 'scene': {'objects': 'oops'}})
    assert error.value.status_code == 422
    source = json.loads(json.dumps(CODE)); source['objects'][0]['provenance'] = 'real-run'
    with pytest.raises(HTTPException):
        transition(None, {'kind': 'open', 'scene': source})


def test_prepared_scenes_open_without_a_model_and_accept_student_actions(tmp_path):
    from athena_api.playground.bridge import prepared_scenes
    prepared_scenes.cache_clear()
    client, service, student, offering, session, base = setup(tmp_path)
    listed = {s['id'] for s in client.get(base + '/prepared').json()}
    assert {'bubble-sort', 'pendulum-g', 'galvanic-cells'} <= listed
    body = {'operation_id': 'open-bubble', 'revision': 0, 'catalog_version': '1.0.0', 'command': {}}
    opened = client.post(base + '/prepared/bubble-sort', json=body)
    assert opened.status_code == 200, opened.text
    assert opened.json()['snapshot']['scene']['id'] == 'bubble-sort' and opened.json()['revision'] == 1
    assert client.post(base + '/prepared/bubble-sort', json=body).json() == opened.json()  # Idempotent replay.
    swap = command(client, base, 'first-swap', 1, {'kind': 'action', 'action': {'objectId': 'bench', 'type': 'swap', 'index': 0}})
    assert swap.status_code == 200, swap.text
    assert client.post(base + '/prepared/not-a-scene', json={**body, 'operation_id': 'open-missing'}).status_code == 404
    # Students choose a prepared scene by id; they still can't open scene content of their own.
    assert command(client, base, 'own-scene', 2, {'kind': 'open', 'scene': SCENE}).status_code == 422
    stranger, _ = browser(tmp_path / 'host.db')
    assert stranger.post(base + '/prepared/bubble-sort', json={**body, 'operation_id': 'open-other'}).status_code == 404
