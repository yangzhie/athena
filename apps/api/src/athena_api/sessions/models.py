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
    environment_id: str | None = None
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
    #: When the lecturer last replied in this session (for the student's "new reply" marker).
    last_lecturer_reply_at: datetime | None = None


class Message(Model):
    id: NonBlank
    session_id: NonBlank
    #: lecturer = a reply from the unit's lecturer while the student shares the session.
    role: Literal["tutor", "learner", "lecturer"]
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


class AnswerReceipt(Model):
    """Private retry data, never part of a student or lecturer projection."""

    question_id: NonBlank
    choice_id: str | None
    text: str | None
    hint_used: bool
    messages: list[Message] = Field(default_factory=list)

    def same_submission(self, other: "AnswerReceipt") -> bool:
        return self.model_dump(exclude={"messages"}) == other.model_dump(exclude={"messages"})


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
    last_lecturer_reply_at: datetime | None

    @classmethod
    def of(cls, s: LearningSession) -> "LearningSessionOut":
        return cls(**s.model_dump(exclude={"student_id", "share_token", "environment_id"}))


# --- Lecturer-facing (shared sessions): never the student id or the session id ---------


class SharedSessionSummary(BaseModel):
    #: The anonymous share id (the session's current share token).
    share_id: str
    student_label: str = "Anonymous student"
    title: str
    goal: str
    shared_at: datetime
    updated_at: datetime
    message_count: int


class SharedMessage(BaseModel):
    """A message as a lecturer sees it in a shared session."""

    id: str
    role: Literal["tutor", "learner", "lecturer"]
    content: str
    sources: list[dict]
    knowledge_origin: str | None
    activity: dict | None
    answer_for: str | None
    created_at: datetime


class SharedSessionView(BaseModel):
    session: SharedSessionSummary
    messages: list[SharedMessage]
