from datetime import UTC, datetime

import pytest
from .http_client import TestClient

from athena_api.app import create_app
from athena_api.sessions.service import SessionService
from athena_api.sessions.store import MemorySessionStore
from athena_api.srs.models import Bank, Item, McqVariant, ShortVariant
from athena_api.srs.scheduler import make_scheduler
from athena_api.srs.service import SrsService
from athena_api.srs.store import MemoryStore

OFF = "cse5alg-2026-s2"
BANK_URL = f"/units/{OFF}/srs/bank"


def mcq(id, status="approved", origin="bank"):
    return McqVariant(id=id, stem=f"Question {id}?", options=["O(n)", "O(n²)"], answer_index=1,
                      explanation="Nested shifts.", status=status, origin=origin)


BANK = Bank(offering_id=OFF, items=[
    Item(id="wc", offering_id=OFF, topic_id="insertion-sort", concept="c", difficulty=1, bloom="recall",
         variants=[mcq("a"), mcq("g", "pending", "generated"), mcq("l", "pending", "live")]),
    Item(id="st", offering_id=OFF, topic_id="insertion-sort", concept="s", difficulty=2, bloom="analyse",
         variants=[ShortVariant(id="s1", stem="Stable? Why?", model_answer="Yes", rubric=["order kept"], explanation="e",
                                status="pending", origin="generated")]),
])


@pytest.fixture
def setup():
    store = MemoryStore()
    store.put_bank(BANK)
    srs = SrsService(store, clock=lambda: datetime(2026, 11, 10, tzinfo=UTC), scheduler=make_scheduler(fuzz=False))
    who = {"student": "alice", "lecturer": "dr-liu"}
    app = create_app(srs=srs, sessions=SessionService(MemorySessionStore()),
                     resolve_student=lambda _r: who["student"], resolve_lecturer=lambda _r, _o: who["lecturer"])
    return TestClient(app), store, srs, who


def status_of(store, item, variant):
    return next(i for i in store.get_bank(OFF).items if i.id == item).variant(variant).status


def test_lecturer_sees_the_whole_bank_with_answers(setup):
    client, _, _, _ = setup
    bank = client.get(BANK_URL).json()
    first = bank["items"][0]["variants"][0]
    assert first["answer_index"] == 1 and first["status"] == "approved"
    assert {v["origin"] for v in bank["items"][0]["variants"]} == {"bank", "generated", "live"}


def test_non_lecturers_are_refused(setup):
    client, _, _, who = setup
    who["lecturer"] = None
    assert client.get(BANK_URL).status_code == 403
    assert client.post(f"{BANK_URL}/approve-pending", json={}).status_code == 403


def test_approving_makes_a_wording_visible_to_students(setup):
    client, store, srs, _ = setup
    # Before: the short-answer item has only a pending wording, so students never get it.
    seen = set()
    for _ in range(3):
        q = srs.next("bob", OFF)
        if q["done"]:
            break
        seen.add(q["item_id"])
        r = srs.answer("bob", OFF, q["item_id"], q["question"]["variant_id"], 1 if q["question"]["kind"] == "mcq" else "x")
        srs.rate("bob", OFF, r["attempt_id"], "good")
    assert "st" not in seen
    assert client.post(f"{BANK_URL}/items/st/variants/s1/status", json={"status": "approved"}).status_code == 200
    assert srs.next("carol", OFF)["item_id"] in {"wc", "st"}
    assert status_of(store, "st", "s1") == "approved"


def test_reject_and_undo(setup):
    client, store, _, _ = setup
    client.post(f"{BANK_URL}/items/wc/variants/l/status", json={"status": "rejected"})
    assert status_of(store, "wc", "l") == "rejected"
    client.post(f"{BANK_URL}/items/wc/variants/l/status", json={"status": "pending"})
    assert status_of(store, "wc", "l") == "pending"
    assert client.post(f"{BANK_URL}/items/wc/variants/l/status", json={"status": "gone"}).status_code == 422


def test_edit_validates_and_respects_kind(setup):
    client, store, _, _ = setup
    r = client.patch(f"{BANK_URL}/items/wc/variants/g", json={"stem": "Reworded?", "options": ["O(n²)", "O(1)"], "answer_index": 0})
    assert r.status_code == 200 and r.json()["stem"] == "Reworded?"
    v = next(i for i in store.get_bank(OFF).items if i.id == "wc").variant("g")
    assert v.options[v.answer_index] == "O(n²)" and v.status == "pending"  # editing doesn't approve
    assert client.patch(f"{BANK_URL}/items/wc/variants/g", json={"answer_index": 5}).status_code == 422
    assert client.patch(f"{BANK_URL}/items/wc/variants/g", json={"model_answer": "x"}).status_code == 422
    assert client.patch(f"{BANK_URL}/items/wc/variants/g", json={"status": "approved"}).status_code == 422
    assert client.patch(f"{BANK_URL}/items/st/variants/s1", json={"rubric": ["equal keys keep order"]}).status_code == 200
    assert client.patch(f"{BANK_URL}/items/nope/variants/x", json={"stem": "?"}).status_code == 404


def test_approve_all_pending(setup):
    client, store, _, _ = setup
    assert client.post(f"{BANK_URL}/approve-pending", json={"item_ids": ["st"]}).json() == {"approved": 1}
    assert status_of(store, "wc", "g") == "pending"
    assert client.post(f"{BANK_URL}/approve-pending", json={}).json() == {"approved": 2}
    assert all(v.status == "approved" for i in store.get_bank(OFF).items for v in i.variants)
