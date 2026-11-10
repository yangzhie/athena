from datetime import UTC, datetime, timedelta

import pytest
from .http_client import TestClient

from athena_api.app import create_app
from athena_api.srs.models import Bank, Item, McqVariant, NumericVariant, ShortVariant
from athena_api.srs.scheduler import make_scheduler
from athena_api.srs.service import SrsService
from athena_api.srs.store import MemoryStore, SqliteStore

OFFERING = "cse5alg-2026-s2"
T0 = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)


def mcq(id, stem):
    return McqVariant(id=id, stem=stem, options=["O(n)", "O(n²)", "O(log n)"], answer_index=1, explanation="Nested shifting.")


BANK = Bank(
    offering_id=OFFERING,
    items=[
        Item(id="worst-case", offering_id=OFFERING, topic_id="insertion-sort", concept="Worst case is O(n²).",
             difficulty=1, bloom="recall",
             variants=[mcq("a", "Worst-case time of insertion sort?"), mcq("b", "Which bound fits insertion sort on reversed input?"),
                       mcq("c", "Insertion sort on n items in descending order takes…")]),
        Item(id="folds", offering_id=OFFERING, topic_id="complexity-search", concept="5-fold CV on 1000 rows.",
             difficulty=2, bloom="apply",
             variants=[NumericVariant(id="n1", stem="5 folds, 1000 rows: rows per validation fold?", answer=200.0, explanation="1000/5.")]),
        Item(id="stable", offering_id=OFFERING, topic_id="insertion-sort", concept="Insertion sort is stable.",
             difficulty=3, bloom="analyse",
             variants=[ShortVariant(id="s1", stem="Is insertion sort stable? Why?", model_answer="Yes...", rubric=["equal keys keep order"], explanation="It only shifts strictly greater items.")]),
    ],
)


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now


@pytest.fixture(params=["memory", "sqlite"])
def setup(request, tmp_path):
    store = MemoryStore() if request.param == "memory" else SqliteStore(tmp_path / "t.db")
    store.put_bank(BANK)
    clock = Clock()
    service = SrsService(store, clock=clock, scheduler=make_scheduler(fuzz=False))
    who = {"id": "alice"}
    client = TestClient(create_app(srs=service, resolve_student=lambda _req: who["id"]))
    return client, clock, who


def base(offering=OFFERING):
    return f"/units/{offering}/srs"


def test_questions_never_include_answers(setup):
    client, _, _ = setup
    q = client.get(f"{base()}/next").json()
    assert q["done"] is False and q["is_new"] is True
    assert q["item_id"] == "worst-case"  # easiest new item first
    assert set(q["question"]) == {"variant_id", "kind", "stem", "options"}


def test_wrong_answer_is_recorded_and_comes_back_reworded(setup):
    client, clock, _ = setup
    q = client.get(f"{base()}/next").json()
    first = q["question"]["variant_id"]
    r = client.post(f"{base()}/attempts", json={"item_id": "worst-case", "variant_id": first, "answer": 0}).json()
    assert r["correct"] is False and r["needs_rating"] is False
    assert r["feedback"]["correct_option"] == 1 and "explanation" in r["feedback"]

    clock.now = T0 + timedelta(minutes=15)  # past the learning step
    later = [client.get(f"{base()}/next").json() for _ in range(5)]
    retry = next(q for q in later if q["item_id"] == "worst-case")
    assert retry["question"]["variant_id"] != first
    assert retry["is_new"] is False


def test_right_answer_needs_a_rating_then_moves_out(setup):
    client, _, _ = setup
    v = client.get(f"{base()}/next").json()["question"]["variant_id"]
    r = client.post(f"{base()}/attempts", json={"item_id": "worst-case", "variant_id": v, "answer": 1}).json()
    assert r["correct"] is True and r["rating_options"] == ["hard", "good", "easy"]
    due = client.post(f"{base()}/attempts/{r['attempt_id']}/rating", json={"rating": "good"}).json()["next_due_at"]
    assert datetime.fromisoformat(due) > T0
    # Rating twice is refused; a right answer can't be rated "again".
    assert client.post(f"{base()}/attempts/{r['attempt_id']}/rating", json={"rating": "easy"}).status_code == 409
    r2 = client.post(f"{base()}/attempts", json={"item_id": "worst-case", "variant_id": v, "answer": 1}).json()
    assert client.post(f"{base()}/attempts/{r2['attempt_id']}/rating", json={"rating": "again"}).status_code == 400


def test_short_answers_are_self_rated(setup):
    client, _, _ = setup
    r = client.post(f"{base()}/attempts", json={"item_id": "stable", "variant_id": "s1", "answer": "yes, equal keys stay"}).json()
    assert r["correct"] is None and r["needs_rating"] is True
    assert r["feedback"]["model_answer"] and r["feedback"]["rubric"]
    assert r["rating_options"] == ["again", "hard", "good", "easy"]
    assert client.post(f"{base()}/attempts/{r['attempt_id']}/rating", json={"rating": "again"}).status_code == 200


def test_summary_counts(setup):
    client, _, _ = setup
    s = client.get(f"{base()}/summary").json()
    assert s == {"total_items": 3, "due_now": 0, "new_available": 3, "reviewed_today": 0, "next_due_at": None}
    v = client.get(f"{base()}/next").json()["question"]["variant_id"]
    client.post(f"{base()}/attempts", json={"item_id": "worst-case", "variant_id": v, "answer": 0})
    s = client.get(f"{base()}/summary").json()
    assert (s["new_available"], s["reviewed_today"]) == (2, 1)
    assert s["next_due_at"] is not None


def test_done_when_nothing_is_due(setup):
    client, _, _ = setup
    for item, variant, answer in [("worst-case", "a", 1), ("folds", "n1", 200), ("stable", "s1", "yes")]:
        r = client.post(f"{base()}/attempts", json={"item_id": item, "variant_id": variant, "answer": answer}).json()
        client.post(f"{base()}/attempts/{r['attempt_id']}/rating", json={"rating": "good"})
    q = client.get(f"{base()}/next").json()
    assert q["done"] is True and q["next_due_at"]


def test_students_are_isolated(setup):
    client, _, who = setup
    r = client.post(f"{base()}/attempts", json={"item_id": "worst-case", "variant_id": "a", "answer": 1}).json()
    who["id"] = "bob"
    # Bob can't rate Alice's attempt and doesn't see her progress.
    assert client.post(f"{base()}/attempts/{r['attempt_id']}/rating", json={"rating": "good"}).status_code == 404
    assert client.get(f"{base()}/summary").json()["new_available"] == 3


def test_identity_cannot_come_from_the_body(setup):
    client, _, _ = setup
    resp = client.post(f"{base()}/attempts", json={"item_id": "worst-case", "variant_id": "a", "answer": 1, "student_id": "bob"})
    assert resp.status_code == 422


def test_unauthenticated_and_unknown(setup):
    client, _, who = setup
    assert client.get(f"{base('nope')}/next").status_code == 404
    assert client.post(f"{base()}/attempts", json={"item_id": "zzz", "variant_id": "a", "answer": 1}).status_code == 404
    who["id"] = None
    assert client.get(f"{base()}/next").status_code == 401


def test_new_items_are_capped_per_day(tmp_path):
    store = MemoryStore()
    store.put_bank(BANK)
    clock = Clock()
    service = SrsService(store, clock=clock, scheduler=make_scheduler(fuzz=False), new_per_day=1)
    r = service.answer("alice", OFFERING, "worst-case", "a", 1)
    service.rate("alice", OFFERING, r["attempt_id"], "good")
    assert service.next("alice", OFFERING)["done"] is True
    clock.now = T0 + timedelta(days=1)
    assert service.next("alice", OFFERING)["done"] is False
