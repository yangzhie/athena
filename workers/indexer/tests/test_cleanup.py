import json

from athena_indexer.cleanup import build_clips, tidy
from athena_indexer.models import Line, ProposedSegment, Topic

TOPICS = [Topic(id="sort", name="Insertion Sort"), Topic(id="hash", name="Hash Tables")]


def lines(n, step=10.0):
    return [Line(index=i, start_s=i * step, end_s=i * step + step - 0.5, text=f"line {i}.") for i in range(n)]


def seg(a, b, topic="sort", title="Idea", summary="s"):
    return ProposedSegment(first_line=a, last_line=b, topic_id=topic, title=title, summary=summary)


def spans_of(segments, n=100, **kw):
    return [(s.first, s.last, s.topic_id, s.title) for s in tidy(segments, lines(n), **kw)]


def test_noise_is_dropped():
    assert spans_of([seg(0, 4, None, "Admin"), seg(5, 20, "sort", "Inner loop"), seg(21, 30, None, "Break")]) == [
        (5, 20, "sort", "Inner loop")
    ]


def test_short_noise_between_same_topic_is_bridged():
    out = spans_of([seg(0, 20, "sort", "A"), seg(21, 22, None, "Mic check"), seg(23, 40, "sort", "B")])
    assert out[0][:2] == (0, 22)  # bridged into the first
    assert out[1][:2] == (23, 40)


def test_long_noise_or_different_topics_are_not_bridged():
    assert spans_of([seg(0, 20, "sort", "A"), seg(21, 30, None, "Break"), seg(31, 50, "sort", "B")])[0][:2] == (0, 20)
    assert spans_of([seg(0, 20, "sort", "A"), seg(21, 22, None, "x"), seg(23, 40, "hash", "B")])[0][:2] == (0, 20)


def test_same_title_neighbours_merge():
    assert spans_of([seg(0, 10, "sort", "Worked example"), seg(11, 20, "sort", "worked example")]) == [
        (0, 20, "sort", "Worked example")
    ]


def test_too_short_segment_folds_into_same_topic_neighbour():
    # 3 lines = ~30 s < 45 s; the next segment shares its topic.
    out = spans_of([seg(0, 20, "hash", "Hashing"), seg(21, 23, "sort", "Tiny"), seg(24, 40, "sort", "Main")])
    assert out == [(0, 20, "hash", "Hashing"), (21, 40, "sort", "Main")]


def test_longer_segment_keeps_its_title_when_absorbing():
    out = spans_of([seg(0, 2, "sort", "Tiny"), seg(3, 30, "sort", "Main idea", "Main summary")])
    assert out == [(0, 30, "sort", "Main idea")]


def test_build_clips_produces_valid_clips_json():
    ls = lines(60)
    result = build_clips(
        [seg(0, 2, None, "Hello"), seg(3, 30, "sort", "Shifting elements"), seg(31, 59, "hash", "Chaining")],
        ls, TOPICS, recording_id="alg-w2", title="Sorting", duration_s=600.0,
    )
    data = json.loads(result.to_json())
    assert [c["id"] for c in data["clips"]] == ["alg-w2-01", "alg-w2-02"]
    first = data["clips"][0]
    assert (first["startS"], first["endS"]) == (30.0, 309.5)
    assert first["topic"] == "Insertion Sort"
    assert first["transcript"].startswith("line 3. line 4.")
    assert first["approved"] is False


def test_only_noise_gives_no_clips():
    result = build_clips([seg(0, 9, None, "Admin")], lines(10), TOPICS, recording_id="r", title="t", duration_s=100.0)
    assert result.clips == []
