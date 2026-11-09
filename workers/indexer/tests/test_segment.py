import json

import pytest

from athena_indexer.models import Line, Topic
from athena_indexer.segment import (
    SegmentationError,
    check,
    keep_owned,
    plan_windows,
    segment_lines,
    segment_window,
)

TOPICS = [Topic(id="hash", name="Hash Tables"), Topic(id="heaps", name="Heaps")]
IDS = {"hash", "heaps"}


def lines(n, step=10.0):
    """n lines, one every `step` seconds."""
    return [Line(index=i, start_s=i * step, end_s=i * step + step - 1, text=f"line {i}") for i in range(n)]


def seg(a, b, topic="hash", title="t"):
    return {"first_line": a, "last_line": b, "topic_id": topic, "title": title, "summary": "s"}


class FakeModel:
    name = "fake:v1"

    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts = []

    def propose(self, system, user):
        self.prompts.append(user)
        answer = self.answers.pop(0)
        return answer(user) if callable(answer) else answer


# --- check ------------------------------------------------------------------------------


def test_check_accepts_full_ordered_coverage_with_noise():
    segments, problems = check([seg(0, 3, None), seg(4, 9)], 0, 9, IDS)
    assert problems == []
    assert [s.topic_id for s in segments] == [None, "hash"]


@pytest.mark.parametrize(
    "raw, expected",
    [
        ([seg(0, 3), seg(5, 9)], "lines 4-4 are not covered"),
        ([seg(0, 5), seg(4, 9)], "overlaps"),
        ([seg(0, 7)], "lines 8-9 are not covered"),
        ([seg(0, 9, "graphs")], "unknown topic_id 'graphs'"),
        ([seg(0, 12)], "within lines 0-9"),
        ([seg(5, 2), seg(0, 9)], "invalid"),
    ],
)
def test_check_reports_problems(raw, expected):
    _, problems = check(raw, 0, 9, IDS)
    assert any(expected in p for p in problems), problems


# --- retries ------------------------------------------------------------------------------


def test_bad_answer_is_retried_with_problems_listed():
    ls = lines(10)
    [w] = plan_windows(ls)
    model = FakeModel([seg(0, 5)], [seg(0, 9)])
    out = segment_window(model, ls, w, TOPICS)
    assert len(out) == 1
    assert "lines 6-9 are not covered" in model.prompts[1]


def test_gives_up_after_max_attempts():
    ls = lines(10)
    [w] = plan_windows(ls)
    with pytest.raises(SegmentationError, match="no valid answer"):
        segment_window(FakeModel([seg(0, 5)], [seg(0, 5)], [seg(0, 5)]), ls, w, TOPICS)


# --- windows ------------------------------------------------------------------------------


def test_short_lecture_is_one_window():
    [w] = plan_windows(lines(50))
    assert (w.first, w.last, w.own_first, w.own_last) == (0, 49, 0, 49)


def test_long_lecture_windows_overlap_with_contiguous_ownership():
    ls = lines(660)  # 110 minutes, a line every 10 s
    ws = plan_windows(ls, window_s=1200, overlap_s=120)
    assert len(ws) == 6
    assert ws[0].own_first == 0 and ws[-1].own_last == 659
    for a, b in zip(ws, ws[1:]):
        assert a.own_last + 1 == b.own_first
        assert b.first < b.own_first and a.last > a.own_last  # they overlap


def test_keep_owned_trims_to_owned_lines():
    from athena_indexer.segment import Window
    from athena_indexer.models import ProposedSegment

    w = Window(index=1, first=90, last=210, own_first=100, own_last=199)
    out = keep_owned([ProposedSegment(**seg(90, 95)), ProposedSegment(**seg(96, 150)), ProposedSegment(**seg(151, 210))], w)
    assert [(s.first_line, s.last_line) for s in out] == [(100, 150), (151, 199)]


def test_segment_lines_covers_everything_and_uses_cache(tmp_path):
    ls = lines(300)  # 50 minutes

    def cover_window(user):
        header = next(l for l in user.splitlines() if l.startswith("Transcript lines"))
        a, b = map(int, header.removeprefix("Transcript lines ").rstrip(":").split("-"))
        mid = (a + b) // 2
        return [seg(a, mid, "hash"), seg(mid + 1, b, "heaps")]

    model = FakeModel(*[cover_window] * 10)
    out = segment_lines(ls, TOPICS, model, cache_dir=tmp_path, window_s=1200, overlap_s=120)
    covered = [i for s in out for i in range(s.first_line, s.last_line + 1)]
    assert covered == list(range(300))
    calls = len(model.prompts)

    again = FakeModel()  # would fail if called
    assert segment_lines(ls, TOPICS, again, cache_dir=tmp_path, window_s=1200, overlap_s=120) == out
    assert calls == len(list(tmp_path.glob("window-*.json")))


def test_prompt_contains_topics_and_numbered_lines():
    ls = lines(3)
    [w] = plan_windows(ls)
    model = FakeModel([seg(0, 2)])
    segment_window(model, ls, w, TOPICS)
    prompt = model.prompts[0]
    assert json.dumps("hash") in prompt and "Hash Tables" in prompt
    assert "Transcript lines 0-2:" in prompt
    assert "1 [00:10] line 1" in prompt
