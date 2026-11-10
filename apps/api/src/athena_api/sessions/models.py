from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NonBlank = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]


class Model(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class LearningSession(Model):
    """One chat in a unit with a goal the student chose. Private to that student."""

    id: NonBlank
    student_id: NonBlank
    offering_id: NonBlank
    goal: Annotated[str, StringConstraints(min_length=1, max_length=200, pattern=r"\S")]
    title: Annotated[str, StringConstraints(min_length=1, max_length=80, pattern=r"\S")]
    created_at: datetime
    updated_at: datetime
    #: Shared with the unit's lecturers by the student (AGENTS.md, Privacy rule 6).
    shared: bool = False
    shared_at: datetime | None = None
    #: The anonymous id lecturers know this share by. New on every share, so separate
    #: shares can't be linked to each other or to the student. Never sent to students.
    share_token: str | None = None


class Message(Model):
    id: NonBlank
    session_id: NonBlank
    role: Literal["tutor", "learner"]
    content: NonBlank
    #: Tutor messages: the material the reply is based on (agent SourceReference dicts).
    sources: list[dict] = Field(default_factory=list)
    knowledge_origin: Literal["materials", "supplement", "general"] | None = None
    #: Tutor messages from the agent: the learner-facing activity (question, explanation,
    #: feedback, ...) as JSON. Never contains answers or grading criteria.
    activity: dict | None = None
    #: Learner messages that answer a question: that question's id.
    answer_for: str | None = None
    created_at: datetime


class LearningSessionOut(BaseModel):
    """What the student gets back: no student id."""

    id: str
    offering_id: str
    goal: str
    title: str
    created_at: datetime
    updated_at: datetime
    shared: bool
    shared_at: datetime | None

    @classmethod
    def of(cls, s: LearningSession) -> "LearningSessionOut":
        return cls(**s.model_dump(exclude={"student_id", "share_token"}))
