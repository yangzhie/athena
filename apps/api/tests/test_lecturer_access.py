import hashlib
import time
from concurrent.futures import ThreadPoolExecutor

from athena_api.spaces.service import StudySpaces
from .test_study_spaces import clients, BODY
from .http_client import TestClient


def test_students_cannot_create_or_upload_even_with_forged_role_and_old_management_grant(tmp_path):
    spaces, _, lecturer, student = clients(tmp_path)
    assert student.get('/identity').json()['role'] == 'student'
    for headers in ({}, {'X-Role': 'lecturer', 'X-Lecturer-Id': 'admin'}):
        response = student.post('/offerings', json=BODY, headers=headers)
        assert response.status_code == 403
    assert spaces.db.execute('SELECT count(*) FROM units').fetchone()[0] == 0
    offering = lecturer.post('/offerings', json=BODY).json()['id']
    lecturer.post(f'/offerings/{offering}/publish')
    sid, _ = spaces.identity(student.cookies.get('athena_session'))
    # Legacy creator grants from the former open-creation policy are insufficient.
    with spaces.db:
        spaces.db.execute('INSERT INTO management_grants VALUES (?,?,?)', (offering, sid, 'legacy-capability'))
    assert student.get(f'/offerings/{offering}').json()['can_manage'] is False
    for path, body in [(f'/offerings/{offering}/publish', None), (f'/units/{offering}/topics', {'title': 'Forbidden'})]:
        assert student.post(path, json=body).status_code == 403
    assert student.post(f'/units/{offering}/materials?filename=notes.txt', content=b'Forbidden upload').status_code == 403
    assert student.delete(f'/offerings/{offering}').status_code == 403
    assert student.get(f'/units/{offering}/lectures/review').status_code == 403
    assert student.post(f'/units/{offering}/sessions', json={'goal': 'Clustering'}).status_code == 201
    assert student.get(f'/units/{offering}/progress').status_code == 200


def test_invites_are_hashed_expire_and_cannot_be_replayed_or_escalate_another_offering(tmp_path):
    spaces, _, lecturer, student = clients(tmp_path)
    offering = lecturer.post('/offerings', json=BODY).json()['id']
    lecturer.post(f'/offerings/{offering}/publish')
    invite = spaces.create_lecturer_invite()
    stored = spaces.db.execute('SELECT token_hash FROM lecturer_invites').fetchone()[0]
    assert stored == hashlib.sha256(invite.encode()).hexdigest() and stored != invite
    assert student.post('/identity/lecturer-access', json={'code': 'wrong-code-' * 4}).status_code == 403
    assert student.post('/identity/lecturer-access', json={'code': invite, 'student_id': 'forged'}).status_code == 422
    assert student.post('/identity/lecturer-access', json={'code': invite}).json()['role'] == 'lecturer'
    other = TestClient(lecturer.app)
    assert other.post('/identity/lecturer-access', json={'code': invite}).status_code == 403
    assert student.get(f'/units/{offering}/lectures/review').status_code == 403
    assert student.post(f'/units/{offering}/materials?filename=test.txt', content=b'Forbidden').status_code == 403
    own = student.post('/offerings', json={**BODY, 'code': 'OWN'}).json()['id']
    assert student.post(f'/units/{own}/materials?filename=test.txt', content=b'Lecture notes').status_code == 202
    expired = spaces.create_lecturer_invite()
    with spaces.db:
        spaces.db.execute('UPDATE lecturer_invites SET expires_at=?', (time.time()-1,))
    assert other.post('/identity/lecturer-access', json={'code': expired}).status_code == 403
    # Server grants survive API restart but are not carried by an arbitrary role header.
    restored = StudySpaces(spaces.path)
    sid, _ = restored.identity(student.cookies.get('athena_session'))
    assert restored.is_lecturer(sid)
    restored.close()


def test_one_invite_cannot_authorise_two_browser_identities_concurrently(tmp_path):
    from fastapi import HTTPException
    spaces, _, _, _ = clients(tmp_path)
    invite = spaces.create_lecturer_invite()
    identities = [spaces.identity(None)[0] for _ in range(2)]
    stores = [StudySpaces(spaces.path) for _ in identities]
    def redeem(pair):
        store, identity = pair
        try:
            store.redeem_lecturer_invite(identity, invite)
            return 200
        except HTTPException as error:
            return error.status_code
    with ThreadPoolExecutor() as executor:
        results = list(executor.map(redeem, zip(stores, identities)))
    assert sorted(results) == [200, 403]
    assert sum(spaces.is_lecturer(identity) for identity in identities) == 1
    for store in stores:
        store.close()
