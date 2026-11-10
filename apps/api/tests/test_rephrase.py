import random
from datetime import UTC, datetime

import pytest

from athena_api.srs.models import Bank, Item, McqVariant, NumericVariant
from athena_api.srs.rephrase import RephraseError, check_rewrite, rephrase
from athena_api.srs.scheduler import make_scheduler
from athena_api.srs.service import SrsService
from athena_api.srs.store import MemoryStore

OFF = "o"
T0 = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)


def mcq(id, stem):
    return McqVariant(id=id, stem=stem, options=["O(n)", "O(n²)", "O(log n)"], answer_index=1, explanation="Nested shifts.")


ITEM = Item(id="wc", offering_id=OFF, topic_id="t", concept="Insertion sort is O(n²) in the worst case.",
            difficulty=1, bloom="recall", variants=[mcq("a", "What is the worst-case time of insertion sort?")])
NUM = NumericVariant(id="n", stem="Binary search looks for 25 in [3, 8, 12, 17, 21, 25, 30]. How many probes?",
                     answer=2.0, explanation="17, 25.")


class FakeRephraser:
    name = "fake"

    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts = []

    def rewrite(self, system, user):
        self.prompts.append(user)
        if not self.answers:
            raise RephraseError("down")
        return self.answers.pop(0)


# --- checks ---------------------------------------------------------------------------------


def test_check_accepts_a_real_rewrite():
    assert check_rewrite("Reverse-ordered input is the hardest case for insertion sort. How does its running time grow?",
                         ITEM.variants[0], ITEM.variants) == []


@pytest.mark.parametrize("stem, problem", [
    ("What is the worst-case time of insertion sort?", "too close"),
    ("Short?", "15-600"),
    ("Is insertion sort O(n²) when the input is reversed, and why?", "gives away"),
])
def test_check_rejects_bad_rewrites(stem, problem):
    assert any(problem in p for p in check_rewrite(stem, ITEM.variants[0], ITEM.variants))


def test_check_requires_every_number():
    problems = check_rewrite("Count binary search probes to find 25 in a sorted array of seven keys.", NUM, [NUM])
    assert any("missing" in p for p in problems)


# --- rephrase -------------------------------------------------------------------------------


def test_rephrase_keeps_answer_data_and_marks_pending():
    new = rephrase(ITEM, ITEM.variants[0], FakeRephraser("Which bound describes insertion sort when every element must move to the front?"),
                   random.Random(1))
    assert isinstance(new, McqVariant)
    assert (new.origin, new.status) == ("live", "pending")
    assert new.options[new.answer_index] == "O(n²)" and sorted(new.options) == sorted(ITEM.variants[0].options)
    assert new.explanation == ITEM.variants[0].explanation


def test_rephrase_retries_with_problems_then_gives_up():
    r = FakeRephraser("What is the worst-case time of insertion sort?",
                      "Which bound describes insertion sort when every element must move to the front?")
    rephrase(ITEM, ITEM.variants[0], r)
    assert "too close" in r.prompts[1]
    with pytest.raises(RephraseError):
        rephrase(ITEM, ITEM.variants[0], FakeRephraser("same?", "same?"))


# --- in the service ---------------------------------------------------------------------------


def service(rephraser):
    store = MemoryStore()
    store.put_bank(Bank(offering_id=OFF, items=[ITEM]))
    return SrsService(store, clock=lambda: T0, scheduler=make_scheduler(fuzz=False), rephraser=rephraser), store


def wrong_once(svc):
    svc.answer("alice", OFF, "wc", "a", 0)


def test_after_every_wording_is_wrong_a_live_one_is_served_and_saved():
    svc, store = service(FakeRephraser("Which bound describes insertion sort when every element must move to the front?"))
    wrong_once(svc)
    svc.clock = lambda: T0.replace(hour=10)
    q = svc.next("alice", OFF)
    assert q["done"] is False and q["question"]["variant_id"].startswith("a-live-")
    saved = store.get_bank(OFF).items[0].variants
    assert len(saved) == 2 and saved[1].status == "pending"
    # The student can answer the live wording, graded with the copied answer.
    assert svc.answer("alice", OFF, "wc", q["question"]["variant_id"], saved[1].answer_index)["correct"] is True


def test_pending_live_wordings_are_not_shown_to_other_students():
    svc, store = service(FakeRephraser("Which bound describes insertion sort when every element must move to the front?"))
    wrong_once(svc)
    svc.clock = lambda: T0.replace(hour=10)
    svc.next("alice", OFF)
    q = svc.next("bob", OFF)
    assert q["question"]["variant_id"] == "a"


def test_without_a_rephraser_an_all_wrong_item_waits():
    svc, _ = service(None)
    wrong_once(svc)
    svc.clock = lambda: T0.replace(hour=10)
    assert svc.next("alice", OFF)["done"] is True  # never repeats the wording they got wrong


def test_failed_rephrase_falls_back_to_an_unwrong_wording():
    item = ITEM.model_copy(update={"variants": [mcq("a", "What is the worst-case time of insertion sort?"),
                                                 mcq("b", "Which input makes insertion sort do the most work?")]})
    store = MemoryStore()
    store.put_bank(Bank(offering_id=OFF, items=[item]))
    svc = SrsService(store, clock=lambda: T0, scheduler=make_scheduler(fuzz=False), rephraser=FakeRephraser())
    svc.answer("alice", OFF, "wc", "b", 1)  # right, b now recent
    r = svc.answer("alice", OFF, "wc", "b", 1)
    svc.rate("alice", OFF, r["attempt_id"], "good")
    svc.answer("alice", OFF, "wc", "a", 0)  # wrong on a: retry needs a new wording; rephraser is down
    svc.clock = lambda: T0.replace(hour=12)
    q = svc.next("alice", OFF)
    assert q["question"]["variant_id"] == "b"


def test_refreshing_reuses_the_live_wording_instead_of_writing_another():
    r = FakeRephraser("Which bound describes insertion sort when every element must move to the front?")
    svc, store = service(r)
    wrong_once(svc)
    svc.clock = lambda: T0.replace(hour=10)
    first = svc.next("alice", OFF)["question"]["variant_id"]
    again = svc.next("alice", OFF)["question"]["variant_id"]  # refresh: rephraser has no more answers
    assert again == first
    assert len(store.get_bank(OFF).items[0].variants) == 2
    assert store.get_card("alice", "wc").live_variant_ids == [first]
