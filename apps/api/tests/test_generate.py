import json

import pytest

from athena_api.srs.generate import Source, check_draft, generate, merge_into, sources_from_clips_json, to_item
from athena_api.srs.models import Bank
from athena_api.srs.starter_banks import cse5alg_bank

TOPICS = [{"id": "insertion-sort", "name": "Insertion Sort"}, {"id": "merge-sort", "name": "Merge Sort"}]
SRC = Source(
    id="rec-01", topic_id="insertion-sort", title="Shifting elements",
    text="So in insertion sort we take the next element and shift every larger element one place to the right. "
         "Then we drop the element into the gap. If the array is already sorted, nothing moves at all.",
)


def variant(stem, kind="mcq"):
    return {"kind": kind, "stem": stem, "options": ["They shift right", "They are swapped to the end", "They are deleted"],
            "answer_index": 0, "model_answer": "They shift one place right.", "rubric": ["shift right"],
            "explanation": "Larger elements make room by shifting right."}


def draft(**over):
    d = {
        "concept": "Insertion sort shifts larger elements right to make room for the key.",
        "topic_id": "insertion-sort", "difficulty": 2, "bloom": "recall",
        "evidence": "shift every larger element one place to the right",
        "variants": [
            variant("During insertion, what happens to elements larger than the key?"),
            variant("Insertion sort is placing 4 into [2, 5, 7]. What does it do with 5 and 7?"),
            variant("Explain how insertion sort makes room for the element it is inserting.", kind="short"),
        ],
    }
    d.update(over)
    return d


class FakeModel:
    name = "fake"

    def __init__(self, items):
        self.items = items
        self.calls = 0

    def draft(self, system, user):
        self.calls += 1
        assert "Transcript:" in user and "insertion-sort" in user
        return self.items


def test_good_draft_passes_checks_and_becomes_a_pending_linked_item():
    assert check_draft(draft(), SRC, {"insertion-sort"}) == []
    item = to_item(draft(), SRC, "cse5alg-2026-s2")
    assert item.id.startswith("gen-") and item.clip_ids == ["rec-01"]
    assert all(v.origin == "generated" and v.status == "pending" for v in item.variants)
    assert [v.kind for v in item.variants] == ["mcq", "mcq", "short"]
    assert to_item(draft(), SRC, "cse5alg-2026-s2").id == item.id  # stable id


@pytest.mark.parametrize("change, problem", [
    ({"evidence": "insertion sort uses a heap to find the minimum"}, "doesn't match"),
    ({"evidence": "we pick a pivot and partition everything around it"}, "doesn't match"),
    ({"evidence": "shift"}, "at least 5 words"),
    ({"topic_id": "graphs"}, "unknown topic_id"),
    ({"variants": [variant("What happens to larger elements?")]}, "3 wordings"),
    ({"variants": [variant("What happens to larger elements during insertion?")] * 3}, "too similar"),
])
def test_bad_drafts_are_caught(change, problem):
    assert any(problem in p for p in check_draft(draft(**change), SRC, {"insertion-sort"}))


def test_generate_reports_accepted_and_rejected():
    bad = draft(concept="Made up", evidence="this sentence is not in the lecture at all")
    broken = draft(concept="Broken options", variants=[{**variant(f"Question number {i} about shifting?"), "answer_index": 7} for i in range(3)])
    report = generate([SRC], TOPICS, "cse5alg-2026-s2", FakeModel([draft(), bad, broken]), per_source=3)
    assert len(report.accepted) == 1
    assert [c for c, _ in report.rejected] == ["Made up", "Broken options"]


def test_merge_keeps_existing_items_and_skips_duplicates():
    item = to_item(draft(), SRC, "cse5alg-2026-s2")
    bank = merge_into(cse5alg_bank(), "cse5alg-2026-s2", [item])
    assert len(bank.items) == len(cse5alg_bank().items) + 1
    again = merge_into(bank, "cse5alg-2026-s2", [item])
    assert len(again.items) == len(bank.items)
    assert merge_into(None, "x", []) == Bank(offering_id="x", items=[])


def test_sources_from_indexer_clips_json(tmp_path):
    path = tmp_path / "clips.json"
    path.write_text(json.dumps({
        "recordingId": "rec", "offeringId": "cse5alg-2026-s2", "clips": [
            {"id": "rec-01", "topicId": "insertion-sort", "title": "Shifting", "transcript": "text one"},
            {"id": "rec-02", "topicId": "merge-sort", "title": "Merging", "transcript": ""},
        ],
    }))
    offering, sources = sources_from_clips_json(path)
    assert offering == "cse5alg-2026-s2"
    assert [s.id for s in sources] == ["rec-01"]  # clips without transcript are skipped


def test_generated_pending_items_are_hidden_from_students():
    from datetime import UTC, datetime

    from athena_api.srs.scheduler import make_scheduler
    from athena_api.srs.service import SrsService
    from athena_api.srs.store import MemoryStore

    store = MemoryStore()
    store.put_bank(Bank(offering_id="o", items=[to_item(draft(), SRC, "o")]))
    svc = SrsService(store, clock=lambda: datetime(2026, 11, 10, tzinfo=UTC), scheduler=make_scheduler(fuzz=False))
    assert svc.next("alice", "o")["done"] is True


def test_near_quotes_are_accepted():
    # One word tidied ("a" for "one") and a filler dropped: still clearly from the lecture.
    near = draft(evidence="take the next element and shift every larger element a place to the right")
    assert check_draft(near, SRC, {"insertion-sort"}) == []


def test_duplicate_ideas_are_rejected():
    twin = draft(concept="Insertion sort shifts larger elements to the right to make room for the key.")
    report = generate([SRC], TOPICS, "o", FakeModel([draft(), twin]), per_source=2)
    assert len(report.accepted) == 1
    assert "duplicates" in report.rejected[0][1][0]
    existing = [to_item(draft(), SRC, "o")]
    again = generate([SRC], TOPICS, "o", FakeModel([twin]), per_source=1, existing=existing)
    assert again.accepted == []
