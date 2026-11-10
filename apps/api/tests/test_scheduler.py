import random
from datetime import UTC, datetime, timedelta

import pytest

from athena_api.srs.models import Item, McqVariant, NumericVariant, ShortVariant
from athena_api.srs.scheduler import (
    ReviewError,
    grade,
    is_due,
    make_scheduler,
    new_card,
    pick_variant,
    review,
)

NOW = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)
SCHED = make_scheduler(fuzz=False)


def mcq(id, status="approved"):
    return McqVariant(id=id, stem=f"wording {id}", options=["O(n)", "O(n²)"], answer_index=1, explanation="e", status=status)


def make_item(n=4, **kw):
    return Item(
        id="i1", offering_id="o", topic_id="t", concept="c", difficulty=2, bloom="recall",
        variants=[mcq(f"v{i}") for i in range(1, n + 1)], **kw,
    )


# --- pick_variant ------------------------------------------------------------------------


def test_new_card_is_due_now_and_gets_any_wording():
    card = new_card("s1", "i1", NOW)
    assert is_due(card, NOW) and not is_due(card, NOW - timedelta(seconds=1))
    assert pick_variant(make_item(), card, random.Random(0)).variant is not None


def test_never_repeats_a_wording_the_student_got_wrong():
    item = make_item(4)
    card = new_card("s1", "i1", NOW)
    card, _ = review(card, item, "v1", correct=False, rating="again", now=NOW, scheduler=SCHED)
    for seed in range(50):
        assert pick_variant(item, card, random.Random(seed)).variant.id != "v1"


def test_prefers_wordings_not_seen_recently():
    item = make_item(4)
    card = new_card("s1", "i1", NOW).model_copy(update={"recent_variant_ids": ["v1", "v2", "v3"]})
    assert {pick_variant(item, card, random.Random(s)).variant.id for s in range(20)} == {"v4"}


def test_reuses_least_recent_wording_after_correct_answers():
    item = make_item(2)
    card = new_card("s1", "i1", NOW).model_copy(update={"recent_variant_ids": ["v2", "v1"]})
    pick = pick_variant(item, card)
    assert pick.variant.id == "v2" and pick.reason == "least recently seen wording"


def test_retry_with_no_fresh_wording_asks_for_live_rephrase():
    item = make_item(2)
    card = new_card("s1", "i1", NOW)
    card, _ = review(card, item, "v2", correct=True, rating="good", now=NOW, scheduler=SCHED)
    card, _ = review(card, item, "v1", correct=False, rating="again", now=NOW, scheduler=SCHED)
    pick = pick_variant(item, card)  # only v2 is left and it was just seen
    assert pick.variant is None and "rephrase" in pick.reason


def test_all_wordings_wrong_asks_for_live_rephrase():
    item = make_item(1)
    card = new_card("s1", "i1", NOW)
    card, _ = review(card, item, "v1", correct=False, rating="again", now=NOW, scheduler=SCHED)
    assert pick_variant(item, card).variant is None


def test_pending_wordings_are_not_shown():
    item = Item(id="i1", offering_id="o", topic_id="t", concept="c", difficulty=1, bloom="recall",
                variants=[mcq("v1"), mcq("v2", status="pending")])
    card = new_card("s1", "i1", NOW)
    assert {pick_variant(item, card, random.Random(s)).variant.id for s in range(20)} == {"v1"}


# --- grade -----------------------------------------------------------------------------------


def test_grade_each_format():
    assert grade(mcq("v"), 1) is True
    assert grade(mcq("v"), 0) is False
    assert grade(mcq("v"), True) is False  # a bool isn't an option index
    num = NumericVariant(id="n", stem="s", answer=200.0, tolerance=0.5, explanation="e")
    assert grade(num, 200.4) is True and grade(num, "200") is True
    assert grade(num, 201) is False and grade(num, "two hundred") is False
    short = ShortVariant(id="s", stem="s", model_answer="m", rubric=["r"], explanation="e")
    assert grade(short, "anything") is None


# --- review ------------------------------------------------------------------------------------


def test_wrong_answer_comes_back_within_the_session():
    item = make_item()
    card, log = review(new_card("s1", "i1", NOW), item, "v1", correct=False, rating="again", now=NOW, scheduler=SCHED)
    assert NOW < card.due <= NOW + timedelta(minutes=10)
    assert card.wrong_variant_ids == ["v1"] and card.recent_variant_ids == ["v1"]
    assert (log.correct, log.rating, log.variant_id) == (False, "again", "v1")


def test_correct_answers_push_the_next_review_further_out():
    item = make_item()
    card = new_card("s1", "i1", NOW)
    t = NOW
    gaps = []
    for variant in ["v1", "v2", "v3", "v4"]:
        card, _ = review(card, item, variant, correct=True, rating="good", now=t, scheduler=SCHED)
        gaps.append(card.due - t)
        t = card.due
    assert gaps == sorted(gaps) and gaps[-1] > timedelta(days=1)
    assert card.recent_variant_ids == ["v2", "v3", "v4"]  # only the last RECENT are kept
    assert card.wrong_variant_ids == []


def test_review_rejects_inconsistent_input():
    item = make_item()
    card = new_card("s1", "i1", NOW)
    with pytest.raises(ReviewError, match="must be rated 'again'"):
        review(card, item, "v1", correct=False, rating="good", now=NOW)
    with pytest.raises(ReviewError, match="can't be rated 'again'"):
        review(card, item, "v1", correct=True, rating="again", now=NOW)
    with pytest.raises(ReviewError, match="no variant"):
        review(card, item, "v9", correct=True, rating="good", now=NOW)
    with pytest.raises(ReviewError, match="don't match"):
        review(new_card("s1", "other", NOW), item, "v1", correct=True, rating="good", now=NOW)


def test_self_assessed_short_answer_can_take_any_rating():
    item = make_item()
    card, log = review(new_card("s1", "i1", NOW), item, "v1", correct=None, rating="hard", now=NOW, scheduler=SCHED)
    assert log.correct is None and card.wrong_variant_ids == []
