"""Private host journal. Pending operations are retried, never reported as success."""

from typing import Literal

from pydantic import Field

from .models import LearningSession, Message, Model
from .tutor import TutorError


class Operation(Model):
    id: str
    kind: Literal["start", "message", "answer", "continue"]
    session: LearningSession
    payload: dict
    shown: str | None = None
    messages: list[Message] = Field(default_factory=list)
    complete: bool = False
    error: str | None = None


def match(previous: Operation, submitted: Operation) -> Operation:
    if (previous.kind, previous.payload) != (submitted.kind, submitted.payload) or (previous.kind != "start" and previous.session.id != submitted.session.id):
        raise TutorError("Operation identifier already used for a different request.", 409)
    return previous.model_copy(deep=True)


SCHEMA = """
CREATE TABLE IF NOT EXISTS session_operations (
    student_id TEXT NOT NULL,
    offering_id TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    complete INTEGER NOT NULL,
    data TEXT NOT NULL,
    PRIMARY KEY(student_id, offering_id, operation_id)
);
CREATE INDEX IF NOT EXISTS operations_by_session ON session_operations(session_id, complete);
"""
