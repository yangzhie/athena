import json

import pytest
from pydantic import ValidationError

from athena_indexer.models import Clip, IndexResult, Line, ProposedSegment, Transcript, TranscriptSegment


def clip(id="c1", start=10.0, end=70.0, recording_id="rec-1", **kw):
    return Clip(
        id=id,
        recording_id=recording_id,
        start_s=start,
        end_s=end,
        topic_id="cv",
        topic="Cross-validation",
        title="k-fold walkthrough",
        summary="Splitting data into k folds.",
        transcript="So we split the data into k folds...",
        **kw,
    )


def test_time_range_must_be_ordered():
    with pytest.raises(ValidationError):
        TranscriptSegment(start_s=5.0, end_s=5.0, text="hi")
    with pytest.raises(ValidationError):
        Line(index=0, start_s=-1.0, end_s=2.0, text="hi")


def test_blank_text_rejected():
    with pytest.raises(ValidationError):
        TranscriptSegment(start_s=0.0, end_s=1.0, text="   ")


def test_transcript_segment_cannot_outlast_recording():
    with pytest.raises(ValidationError):
        Transcript(recording_id="r", duration_s=60.0, segments=[TranscriptSegment(start_s=0.0, end_s=90.0, text="x")])


def test_proposed_segment_line_order_and_noise():
    noise = ProposedSegment(first_line=3, last_line=5, topic_id=None, title="Admin", summary="Assignment dates.")
    assert noise.topic_id is None
    with pytest.raises(ValidationError):
        ProposedSegment(first_line=5, last_line=3, topic_id="cv", title="t", summary="s")


def test_strict_models_reject_unknown_fields_and_coercion():
    with pytest.raises(ValidationError):
        ProposedSegment(first_line="1", last_line=2, topic_id="cv", title="t", summary="s")
    with pytest.raises(ValidationError):
        ProposedSegment(first_line=1, last_line=2, topic_id="cv", title="t", summary="s", start_s=0.0)


def test_index_result_serialises_camel_case_for_frontend():
    result = IndexResult(recording_id="rec-1", title="Model evaluation", duration_s=3000.0, status="ready", clips=[clip()])
    data = json.loads(result.to_json())
    assert data["recordingId"] == "rec-1"
    assert data["durationS"] == 3000.0
    c = data["clips"][0]
    assert {"id", "recordingId", "startS", "endS", "topic", "title", "summary"} <= c.keys()
    # Round-trips from the camelCase file.
    assert IndexResult.model_validate_json(result.to_json()) == result


def test_index_result_rejects_overlap_and_foreign_clips():
    with pytest.raises(ValidationError):
        IndexResult(
            recording_id="rec-1", title="t", duration_s=3000.0, status="ready",
            clips=[clip("a", 10.0, 70.0), clip("b", 60.0, 120.0)],
        )
    with pytest.raises(ValidationError):
        IndexResult(recording_id="rec-1", title="t", duration_s=3000.0, status="ready", clips=[clip(recording_id="other")])


def test_clip_maps_to_agent_video_segment():
    seg = clip().to_video_segment()
    assert seg == {
        "kind": "video",
        "source_id": "rec-1",
        "segment_id": "c1",
        "title": "k-fold walkthrough",
        "transcript": "So we split the data into k folds...",
        "start_seconds": 10.0,
        "end_seconds": 70.0,
    }
