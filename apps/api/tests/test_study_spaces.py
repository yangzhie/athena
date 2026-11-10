"""Real routes and databases: independent browser identities share material, not learning."""
from athena_api.app import create_app
from athena_api.lectures.service import LectureService
from athena_api.lectures.store import MemoryLectureStore
from athena_api.sessions.service import SessionService
from athena_api.sessions.store import SqliteSessionStore
from athena_api.sessions.tutor import PlaceholderTutor
from athena_api.spaces.service import StudySpaces
from athena_api.srs.service import SrsService
from athena_api.srs.store import MemoryStore
from .http_client import TestClient

BODY = {'code': 'CSE5DMI', 'title': 'Data Mining', 'year': 2026, 'semester': 'Semester 2'}


def clients(tmp_path):
    spaces = StudySpaces(tmp_path / 'host.db')
    sessions = SessionService(SqliteSessionStore(tmp_path / 'host.db'), tutor=PlaceholderTutor())
    app = create_app(spaces=spaces, sessions=sessions, srs=SrsService(MemoryStore()),
                     lectures=LectureService(MemoryLectureStore()))
    return spaces, sessions, TestClient(app), TestClient(app)


def test_creator_drafts_publication_and_management_are_persistent(tmp_path):
    spaces, _, alice, bob = clients(tmp_path)
    draft = alice.post('/offerings', json=BODY)
    assert draft.status_code == 201
    item = draft.json()
    assert item['status'] == 'draft' and item['can_manage'] is True
    assert 'student_id' not in draft.text and 'capability' not in draft.text
    cookie = draft.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'SameSite=lax' in cookie
    id = item['id']
    assert bob.get('/offerings').json() == []
    assert bob.get(f'/offerings/{id}').status_code == 404
    assert alice.post(f'/units/{id}/sessions', json={'goal': 'Clustering'}).status_code == 409
    assert alice.post(f'/offerings/{id}/publish').json()['status'] == 'published'
    assert bob.get('/offerings').json()[0]['can_manage'] is False
    assert bob.post(f'/offerings/{id}/publish').status_code == 403
    assert bob.delete(f'/offerings/{id}').status_code == 403
    reopened = StudySpaces(tmp_path / 'host.db')
    token = alice.cookies.get('athena_session')
    student, replacement = reopened.identity(token)
    assert replacement is None and reopened.manages(student, id)
    assert reopened.get(student, id)['status'] == 'published'
    reopened.close()


def test_two_browsers_get_distinct_owned_environments_and_fresh_sessions(tmp_path):
    spaces, service, alice, bob = clients(tmp_path)
    id = alice.post('/offerings', json=BODY).json()['id']
    alice.post(f'/offerings/{id}/publish')
    base = f'/units/{id}/sessions'
    a = alice.post(base, json={'goal': 'Clustering'}).json()
    b = bob.post(base, json={'goal': 'Clustering'}).json()
    assert a['session']['id'] != b['session']['id']
    assert bob.get(base + '/' + a['session']['id']).status_code == 404
    assert alice.get(base + '/' + b['session']['id']).status_code == 404
    assert alice.get(base, headers={'X-Student-Id': 'bob'}).json()[0]['id'] == a['session']['id']
    assert bob.post(base, json={'goal': 'Clustering', 'student_id': 'alice'}).status_code == 422
    first = alice.get(base + '/' + a['session']['id']).json()['messages']
    second = alice.post(base, json={'goal': 'Clustering'}).json()
    assert not set(m['id'] for m in first).intersection(m['id'] for m in second['messages'])
    with spaces.lock:
        rows = spaces.db.execute('SELECT id, student_id, offering_id FROM environments').fetchall()
    assert len(rows) == 2 and rows[0][0] != rows[1][0]
    for environment, student, offering in rows:
        assert all(s.environment_id == environment for s in service.list(student, offering))


def test_unit_roles_and_forged_cookies_never_grant_management(tmp_path, monkeypatch):
    _, _, alice, bob = clients(tmp_path)
    id = alice.post('/offerings', json=BODY).json()['id']
    alice.post(f'/offerings/{id}/publish')
    monkeypatch.setenv('ATHENA_DEV_LECTURER_ID', 'invented')
    assert bob.get(f'/units/{id}/lectures/review', headers={'X-Role': 'lecturer'}).status_code == 403
    assert alice.get(f'/units/{id}/lectures/review').status_code == 200
    other = bob.post('/offerings', json={**BODY, 'code': 'CSE5ALG', 'title': 'Algorithms'}).json()['id']
    bob.post(f'/offerings/{other}/publish')
    assert alice.get(f'/units/{other}/lectures/review').status_code == 403
    alice.cookies.clear()
    alice.cookies.set('athena_session', 'invented-student-id')
    assert alice.get(f'/units/{id}/lectures/review').status_code == 403


def test_unknown_unpublished_and_deleted_offerings_block_all_scoped_routes(tmp_path):
    _, _, alice, bob = clients(tmp_path)
    id = alice.post('/offerings', json=BODY).json()['id']
    for suffix in ['sessions', 'srs/summary', 'lectures', 'lectures/anything/media']:
        assert bob.get(f'/units/{id}/{suffix}').status_code == 404
        assert bob.get(f'/units/missing/{suffix}').status_code == 404
    alice.post(f'/offerings/{id}/publish')
    alice.delete(f'/offerings/{id}')
    assert bob.get(f'/units/{id}/sessions').status_code == 410
    assert bob.get('/offerings').json() == []


def test_cross_origin_mutations_and_identity_fields_are_rejected(tmp_path):
    _, _, alice, _ = clients(tmp_path)
    assert alice.post('/offerings', json=BODY, headers={'Origin': 'https://other.test'}).status_code == 403
    assert alice.post('/offerings', json=BODY, headers={'Sec-Fetch-Site': 'cross-site'}).status_code == 403
    assert alice.post('/offerings', json={**BODY, 'student_id': 'bob'}).status_code == 422
    assert alice.post('/offerings', json=BODY, headers={'Origin': 'http://testserver'}).status_code == 201


def test_concurrent_environment_connections_preserve_one_pair(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    spaces, _, alice, _ = clients(tmp_path)
    id = alice.post('/offerings', json=BODY).json()['id']
    alice.post(f'/offerings/{id}/publish')
    student, _ = spaces.identity(alice.cookies.get('athena_session'))
    stores = [StudySpaces(tmp_path / 'host.db') for _ in range(4)]
    with ThreadPoolExecutor() as executor:
        environments = list(executor.map(lambda store: store.environment(student, id), stores))
    assert len(set(environments)) == 1
    for store in stores:
        store.close()
