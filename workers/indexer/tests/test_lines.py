import pytest

from athena_indexer.lines import render, split_sentences, to_lines
from athena_indexer.models import Transcript, TranscriptSegment


def transcript(*segments, duration=600.0):
    return Transcript(
        recording_id="rec",
        duration_s=duration,
        segments=[TranscriptSegment(start_s=a, end_s=b, text=t) for a, b, t in segments],
    )


def test_split_sentences_handles_questions_quotes_and_abbreviations():
    assert split_sentences("Is it sorted? Yes. We stop.") == ["Is it sorted?", "Yes.", "We stop."]
    assert split_sentences('He said "done." Then left.') == ['He said "done."', "Then left."]
    assert split_sentences("Use a tree, e.g. a red-black tree. Then search.") == [
        "Use a tree, e.g. a red-black tree.",
        "Then search.",
    ]
    assert split_sentences("Bubble sort is O(n²). Fine.") == ["Bubble sort is O(n²).", "Fine."]


def test_multi_sentence_segment_is_split_with_interpolated_times():
    lines = to_lines(transcript((10.0, 20.0, "First we compare adjacent pairs. Then we swap them if needed.")))
    assert [l.text for l in lines] == ["First we compare adjacent pairs.", "Then we swap them if needed."]
    assert lines[0].start_s == 10.0 and lines[1].end_s == 20.0
    assert lines[0].end_s == pytest.approx(lines[1].start_s)
    assert 14.0 < lines[0].end_s < 16.0  # split roughly by text length


def test_sentence_across_segments_is_joined():
    lines = to_lines(transcript((0.0, 3.0, "So the outer loop runs"), (3.0, 6.0, "n minus one times.")))
    assert [l.text for l in lines] == ["So the outer loop runs n minus one times."]
    assert (lines[0].start_s, lines[0].end_s) == (0.0, 6.0)


def test_short_filler_joins_the_next_line():
    lines = to_lines(transcript((0.0, 1.0, "OK."), (1.2, 4.0, "Let's look at hashing today.")))
    assert [l.text for l in lines] == ["OK. Let's look at hashing today."]


def test_long_pause_ends_a_line_even_mid_sentence():
    lines = to_lines(transcript((0.0, 3.0, "And the answer is"), (10.0, 12.0, "forty two, right?")))
    assert len(lines) == 2


def test_lines_never_exceed_max_duration():
    segs = [(i * 5.0, i * 5.0 + 5.0, "and then we keep going") for i in range(20)]  # 100 s, no full stop
    lines = to_lines(transcript(*segs), max_line_s=30.0)
    assert all(l.end_s - l.start_s <= 30.0 for l in lines)
    assert " ".join(l.text for l in lines) == " ".join(t for _, _, t in segs)  # nothing lost


def test_indices_are_contiguous_and_times_ordered():
    lines = to_lines(transcript(
        (0.0, 4.0, "Welcome back everyone. Today is sorting."),
        (4.5, 9.0, "Bubble sort first. It's simple but slow."),
        (9.5, 12.0, "Questions so far?"),
    ))
    assert [l.index for l in lines] == list(range(len(lines)))
    assert all(a.start_s <= b.start_s for a, b in zip(lines, lines[1:]))


def test_render_is_compact_and_indexed():
    lines = to_lines(transcript((65.0, 70.0, "Hash maps give constant time lookups."), (3725.0, 3730.0, "That's all for today folks."), duration=4000.0))
    assert render(lines).splitlines() == [
        "0 [01:05] Hash maps give constant time lookups.",
        "1 [1:02:05] That's all for today folks.",
    ]


def test_empty_transcript():
    assert to_lines(transcript()) == []
