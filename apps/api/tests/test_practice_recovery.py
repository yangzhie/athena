"""Practice commits exactly once across transport retries, failures and restarts."""
from concurrent.futures import ThreadPoolExecutor

import pytest

from athena_api.srs.service import SrsService
from athena_api.srs.store import MemoryStore, SqliteStore
from .test_srs_api import BANK, OFFERING, Clock, base
from .http_client import TestClient
from athena_api.app import create_app


def service(store):
    store.put_bank(BANK)
    return SrsService(store, clock=Clock())


def client(srs, student='alice'):
    return TestClient(create_app(srs=srs, resolve_student=lambda _request: student))


@pytest.mark.parametrize('kind', ['memory', 'sqlite'])
def test_answer_retry_replays_original_grade_and_never_schedules_twice(tmp_path, kind):
    store = MemoryStore() if kind == 'memory' else SqliteStore(tmp_path / 'srs.db')
    srs = service(store)
    browser = client(srs)
    payload = {'item_id': 'worst-case', 'variant_id': 'a', 'answer': 0}
    headers = {'Idempotency-Key': 'same-answer'}
    first = browser.post(base() + '/attempts', json=payload, headers=headers)
    assert first.status_code == 200
    assert browser.post(base() + '/attempts', json=payload, headers=headers).json() == first.json()
    assert browser.get(base() + '/summary').json()['reviewed_today'] == 1
    assert browser.post(base() + '/attempts', json={**payload, 'answer': 1}, headers=headers).status_code == 409
    assert browser.get(base() + '/summary').json()['reviewed_today'] == 1
    assert browser.post(base() + '/operations/answer:same-answer/retry').json() == first.json()
    assert client(srs, 'bob').post(base() + '/operations/answer:same-answer/retry').status_code == 404


def test_rating_receipt_and_pending_feedback_survive_restart(tmp_path):
    path = tmp_path / 'srs.db'
    store = SqliteStore(path)
    browser = client(service(store))
    payload = {'item_id': 'worst-case', 'variant_id': 'a', 'answer': 1}
    original = browser.post(base() + '/attempts', json=payload, headers={'Idempotency-Key': 'correct'}).json()
    pending = browser.get(base() + '/pending').json()
    assert pending['restored_attempt'] == original
    assert 'answer_index' not in pending['question']
    path_for_rating = base() + f"/attempts/{original['attempt_id']}/rating"
    first = browser.post(path_for_rating, json={'rating': 'good'}, headers={'Idempotency-Key': 'rating'})
    assert first.status_code == 200
    store.close()
    reopened = SqliteStore(path)
    browser = client(SrsService(reopened, clock=Clock()))
    assert browser.post(path_for_rating, json={'rating': 'good'}, headers={'Idempotency-Key': 'rating'}).json() == first.json()
    assert browser.get(base() + '/summary').json()['reviewed_today'] == 1
    assert browser.get(base() + '/pending').json() is None
    assert browser.post(path_for_rating, json={'rating': 'easy'}, headers={'Idempotency-Key': 'rating'}).status_code == 409
    reopened.close()


def test_failed_scheduling_rolls_back_attempt_card_log_and_receipt_together(tmp_path):
    store = SqliteStore(tmp_path / 'srs.db')
    srs = service(store)
    with store._db:
        store._db.execute("CREATE TRIGGER fail_log BEFORE INSERT ON review_logs BEGIN SELECT RAISE(ABORT,'simulated disk failure'); END")
    browser = client(srs)
    payload = {'item_id': 'worst-case', 'variant_id': 'a', 'answer': 0}
    headers = {'Idempotency-Key': 'recover'}
    response = browser.post(base() + '/attempts', json=payload, headers=headers)
    assert response.status_code == 503 and 'disk failure' not in response.text
    assert store._db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0] == 0
    assert store._db.execute('SELECT COUNT(*) FROM cards').fetchone()[0] == 0
    assert store._db.execute('SELECT COUNT(*) FROM srs_commands').fetchone()[0] == 0
    with store._db:
        store._db.execute('DROP TRIGGER fail_log')
    assert browser.post(base() + '/attempts', json=payload, headers=headers).status_code == 200
    assert browser.get(base() + '/summary').json()['reviewed_today'] == 1
    store.close()


def test_concurrent_independent_store_connections_accept_one_review(tmp_path):
    path = tmp_path / 'srs.db'
    stores = [SqliteStore(path) for _ in range(4)]
    services = [service(store) for store in stores]
    with ThreadPoolExecutor() as executor:
        results = list(executor.map(lambda s: s.answer('alice', OFFERING, 'worst-case', 'a', 0, 'one-command'), services))
    assert len({r['attempt_id'] for r in results}) == 1
    assert stores[0]._db.execute('SELECT COUNT(*) FROM review_logs').fetchone()[0] == 1
    for store in stores:
        store.close()


def test_private_live_wordings_never_enter_the_lecturer_bank(tmp_path):
    from .test_learning_memory import browser as learning_browser, journey
    from .test_study_spaces import BODY
    browser, spaces, memory, tutor, srs, _ = learning_browser(tmp_path)
    offering = browser.post('/offerings', json=BODY).json()['id']
    browser.post(f'/offerings/{offering}/publish')
    srs.store.put_bank(BANK.model_copy(update={'offering_id': offering, 'items': []}))
    student, _ = journey(browser, spaces, tutor, offering)
    item = memory.practice_items(student, offering)[0]
    # An injected rephraser writes a new private variant through the existing path.
    from athena_api.srs.scheduler import new_card
    from unittest.mock import patch
    card = new_card(student, item.id, srs.clock())
    variant = item.variants[0].model_copy(update={'id': 'private-rephrased', 'stem': 'Private alternate wording', 'origin': 'live', 'status': 'pending'})
    srs.rephraser = object()
    with patch('athena_api.srs.service.rephrase', return_value=variant):
        assert srs._new_wording(srs._bank(offering, student), item, card).id == 'private-rephrased'
    assert any(v.id == 'private-rephrased' for v in memory.practice_items(student, offering)[0].variants)
    assert srs.store.get_bank(offering).items == []
    assert 'Private alternate wording' not in browser.get(f'/units/{offering}/srs/bank').text
    assert memory.profile(student)[0]['evidence_count'] == 3
