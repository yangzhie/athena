"""Data passed between pipeline steps, and the clips.json output.

Pipeline: recording → audio → Transcript → Lines → ProposedSegments → Clips.
Times are seconds from the start of the recording.
"""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from pydantic.alias_generators import to_camel

NonBlank = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]
Seconds = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class Model(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class _TimeRange(Model):
    start_s: Seconds
    end_s: Seconds

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.end_s <= self.start_s:
            raise ValueError("end_s must be after start_s")
        return self


# --- Step 2: speech-to-text output --------------------------------------------------


class TranscriptSegment(_TimeRange):
    """One timed piece of speech as returned by the speech-to-text engine."""

    text: NonBlank


class Transcript(Model):
    recording_id: NonBlank
    duration_s: Seconds
    language: str | None = None
    segments: list[TranscriptSegment]

    @model_validator(mode="after")
    def _within_recording(self) -> Self:
        for s in self.segments:
            if s.end_s > self.duration_s + 1:  # allow rounding slack
                raise ValueError("segment ends after the recording")
        return self


# --- Step 3: numbered sentences the LLM refers to -----------------------------------


class Line(_TimeRange):
    """A sentence-sized, numbered piece of the transcript. The LLM cites these by index."""

    index: Annotated[int, Field(ge=0)]
    text: NonBlank


# --- Step 4: what the LLM proposes ----------------------------------------------------


class Topic(Model):
    """A teachable part of the offering, e.g. "Cross-validation"."""

    id: NonBlank
    name: NonBlank
    description: str | None = None


class ProposedSegment(Model):
    """A topic span as line indices (never times), so the LLM can't invent timestamps.

    topic_id None means noise: admin, breaks, off-topic tangents.
    """

    first_line: Annotated[int, Field(ge=0)]
    last_line: Annotated[int, Field(ge=0)]
    topic_id: NonBlank | None
    title: NonBlank
    summary: NonBlank

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.last_line < self.first_line:
            raise ValueError("last_line must not be before first_line")
        return self


# --- Output ---------------------------------------------------------------------------


class _CamelOut(Model):
    """Serialises with camelCase keys, matching the frontend's TypeScript types."""

    model_config = ConfigDict(strict=True, extra="forbid", alias_generator=to_camel, populate_by_name=True)


class Clip(_CamelOut, _TimeRange):
    """A topic-labelled time range over one recording. Matches the frontend's LectureClip."""

    id: NonBlank
    recording_id: NonBlank
    topic_id: NonBlank
    topic: NonBlank
    title: NonBlank
    summary: NonBlank
    transcript: NonBlank
    approved: bool = False

    def to_video_segment(self) -> dict:
        """The agent's VideoSegment retrieval item (agent/src/athena_agent/retrieval.py)."""
        return {
            "kind": "video",
            "source_id": self.recording_id,
            "segment_id": self.id,
            "title": self.title,
            "transcript": self.transcript,
            "start_seconds": self.start_s,
            "end_seconds": self.end_s,
        }


RecordingStatus = Literal["processing", "ready", "failed"]


class IndexResult(_CamelOut):
    """Contents of clips.json for one recording."""

    recording_id: NonBlank
    title: NonBlank
    duration_s: Seconds
    status: RecordingStatus
    #: The offering (study space) this lecture belongs to, e.g. "cse5alg-2026-s2".
    offering_id: NonBlank | None = None
    week: Annotated[int, Field(ge=1)] | None = None
    clips: list[Clip] = Field(default_factory=list)

    @model_validator(mode="after")
    def _clips_valid(self) -> Self:
        last_end = 0.0
        for c in sorted(self.clips, key=lambda c: c.start_s):
            if c.recording_id != self.recording_id:
                raise ValueError("clip belongs to a different recording")
            if c.start_s < last_end:
                raise ValueError("clips overlap")
            if c.end_s > self.duration_s + 1:
                raise ValueError("clip ends after the recording")
            last_end = c.end_s
        return self

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True, indent=2)
