"""Lectures as stored by the API: the indexer's proposal plus the lecturer's review.

Each clip keeps what the indexer proposed and, separately, the lecturer's
decision and edits. Students only ever see approved clips with edits applied,
and never transcripts. The agent gets approved clips' transcripts as material.
"""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from pydantic.alias_generators import to_camel

NonBlank = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]
Seconds = Annotated[float, Field(ge=0, allow_inf_nan=False)]
ReviewStatus = Literal["pending", "approved", "rejected"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProposedClip(Model):
    """A clip as lecture indexing proposed it (fields of the indexer's Clip)."""

    model_config = ConfigDict(extra="ignore", alias_generator=to_camel, populate_by_name=True)

    id: NonBlank
    recording_id: NonBlank
    start_s: Seconds
    end_s: Seconds
    topic_id: NonBlank
    topic: NonBlank
    title: NonBlank
    summary: NonBlank
    transcript: str = ""


class ClipReview(Model):
    status: ReviewStatus = "pending"
    title: NonBlank | None = None
    start_s: Seconds | None = None
    end_s: Seconds | None = None


class StoredClip(Model):
    proposed: ProposedClip
    review: ClipReview = Field(default_factory=ClipReview)

    @property
    def id(self) -> str:
        return self.proposed.id

    @property
    def status(self) -> ReviewStatus:
        return self.review.status

    def effective(self) -> dict:
        """The clip with the lecturer's edits applied."""
        p = self.proposed
        return {
            "id": p.id, "recording_id": p.recording_id, "topic_id": p.topic_id, "topic": p.topic,
            "summary": p.summary,
            "title": self.review.title or p.title,
            "start_s": p.start_s if self.review.start_s is None else self.review.start_s,
            "end_s": p.end_s if self.review.end_s is None else self.review.end_s,
        }


class Lecture(Model):
    id: NonBlank
    offering_id: NonBlank
    title: NonBlank
    week: Annotated[int, Field(ge=1)] | None = None
    duration_s: Seconds
    status: Literal["processing", "ready", "failed"]
    clips: list[StoredClip] = Field(default_factory=list)
    #: Where the recording is on the server (set on import). Streamed by the media route;
    #: never sent to clients.
    media_path: str | None = None

    @model_validator(mode="after")
    def _unique(self) -> Self:
        ids = [c.id for c in self.clips]
        if len(set(ids)) != len(ids):
            raise ValueError("clip ids must be unique within a lecture")
        return self


class IndexerFile(BaseModel):
    """The indexer's clips.json (camelCase)."""

    model_config = ConfigDict(extra="ignore", alias_generator=to_camel, populate_by_name=True)

    recording_id: NonBlank
    title: NonBlank
    duration_s: Seconds
    status: Literal["processing", "ready", "failed"]
    offering_id: NonBlank | None = None
    week: int | None = None
    #: Recording path relative to the clips.json file.
    media: str | None = None
    clips: list[ProposedClip] = Field(default_factory=list)


# --- What the API returns ------------------------------------------------------------


class StudentClip(BaseModel):
    """Approved clip as students see it: no transcript, no review state."""

    id: str
    recording_id: str
    topic_id: str
    topic: str
    title: str
    summary: str
    start_s: float
    end_s: float


class StudentLecture(BaseModel):
    id: str
    offering_id: str
    title: str
    week: int | None
    duration_s: float
    status: str
    clips: list[StudentClip]
    #: Some clips are still waiting for the lecturer.
    under_review: bool
    #: The recording can be played (GET …/lectures/{id}/media).
    has_media: bool


class LecturerClip(StudentClip):
    status: ReviewStatus
    proposed: dict
    #: The lecturer has decided on or edited this clip (so it can be undone).
    decided: bool


class LecturerLecture(BaseModel):
    id: str
    offering_id: str
    title: str
    week: int | None
    duration_s: float
    status: str
    clips: list[LecturerClip]
    has_media: bool
