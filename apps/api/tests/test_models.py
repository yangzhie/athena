from datetime import UTC, datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from athena_api.srs.models import Bank, CardState, Item, McqVariant, NumericVariant, ReviewLogEntry, Variant


def mcq(id="v1", **kw):
    return McqVariant(
        id=id,
        stem="What is insertion sort's worst-case time?",
        options=["O(n)", "O(n log n)", "O(n²)"],
        answer_index=2,
        explanation="Each element may shift past every earlier one.",
        **kw,
    )


def item(id="i1", offering="cse5alg-2026-s2", variants=None):
    return Item(
        id=id,
        offering_id=offering,
        topic_id="insertion-sort",
        concept="Insertion sort is O(n²) in the worst case.",
        difficulty=2,
        bloom="recall",
        variants=[mcq("v1"), mcq("v2")] if variants is None else variants,
    )


def test_mcq_answer_must_be_an_option():
    with pytest.raises(ValidationError, match="answer_index"):
        McqVariant(id="v", stem="s", options=["a", "b"], answer_index=2, explanation="e")


def test_mcq_options_must_differ():
    with pytest.raises(ValidationError, match="different"):
        McqVariant(id="v", stem="s", options=["O(n)", "o(n) "], answer_index=0, explanation="e")


def test_variants_parse_by_kind():
    parsed = TypeAdapter(Variant).validate_python(
        {"kind": "numeric", "id": "n1", "stem": "How many folds?", "answer": 5.0, "explanation": "k=5."}
    )
    assert isinstance(parsed, NumericVariant)


def test_live_variants_default_to_bank_and_approved():
    v = mcq()
    assert (v.origin, v.status) == ("bank", "approved")


def test_item_needs_unique_variants():
    with pytest.raises(ValidationError, match="unique"):
        item(variants=[mcq("v1"), mcq("v1")])
    with pytest.raises(ValidationError):
        item(variants=[])
    assert item().variant("v2").id == "v2"
    assert item().variant("nope") is None


def test_bank_checks_ids_and_offering():
    with pytest.raises(ValidationError, match="unique"):
        Bank(offering_id="cse5alg-2026-s2", items=[item("i1"), item("i1")])
    with pytest.raises(ValidationError, match="offering"):
        Bank(offering_id="cse5alg-2026-s2", items=[item("i1", offering="cse5dmi-2026-s2")])


def test_bank_round_trips_through_json():
    bank = Bank(offering_id="cse5alg-2026-s2", items=[item()])
    assert Bank.model_validate_json(bank.model_dump_json()) == bank


def test_card_and_log_models():
    now = datetime(2026, 11, 10, tzinfo=UTC)
    card = CardState(student_id="s1", item_id="i1", fsrs={"card_id": 1}, due=now)
    assert card.recent_variant_ids == [] and card.last_wrong_variant_id is None
    log = ReviewLogEntry(student_id="s1", item_id="i1", variant_id="v1", correct=False, rating="again", reviewed_at=now)
    assert log.duration_ms is None
    with pytest.raises(ValidationError):
        ReviewLogEntry(student_id="s1", item_id="i1", variant_id="v1", correct=True, rating="perfect", reviewed_at=now)
