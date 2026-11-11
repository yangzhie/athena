"""Lecturer side of shared sessions (AGENTS.md, Privacy rule 6).

Lecturers find a shared session only by its share token, which is new on every
share and cleared when the student stops sharing, so access ends immediately and
separate shares can't be linked. Nothing returned identifies the student: no
student id, no session id.
"""

import hashlib
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .models import LearningSession, Message, SharedMessage, SharedSessionSummary, SharedSessionView
from .store import SessionStore


class NotShared(LookupError):
    pass


def _message_id(token: str, message_id: str) -> str:
    """Per-share message ids, so ids don't carry over between shares."""
    return hashlib.sha256(f"{token}:{message_id}".encode()).hexdigest()[:16]


def _remap(token, value):
    if isinstance(value, list):
        return [_remap(token, item) for item in value]
    if not isinstance(value, dict):
        return value
    output = {}
    for key, item in value.items():
        if key in {'rubric', 'criteria', 'snapshot', 'internal', 'student_id', 'learner_id', 'environment_id', 'session_id'}:
            continue
        if key not in {'source_id', 'passage_id', 'segment_id'} and (key == 'id' or key.endswith('_id')) and isinstance(item, str):
            output[key] = _message_id(token, item)
        elif key.endswith('_ids') and isinstance(item, list):
            output[key] = [_message_id(token, v) if isinstance(v, str) else _remap(token, v) for v in item]
        else:
            output[key] = _remap(token, item)
    return output


@dataclass
class SharedSessions:
    store: SessionStore
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def _find(self, offering_id: str, share_id: str) -> LearningSession:
        s = next((s for s in self.store.shared(offering_id) if s.share_token == share_id), None)
        if s is None:
            raise NotShared("this session isn't shared (any more)")
        return s

    def _summary(self, s: LearningSession) -> SharedSessionSummary:
        return SharedSessionSummary(
            share_id=s.share_token, title=s.title, goal=s.goal, shared_at=s.shared_at, updated_at=s.updated_at,
            message_count=len(self.store.messages(s.student_id, s.id)),
        )

    def list(self, offering_id: str) -> list[SharedSessionSummary]:
        sessions = sorted(self.store.shared(offering_id), key=lambda s: s.updated_at, reverse=True)
        return [self._summary(s) for s in sessions]

    def reply(self, offering_id: str, share_id: str, text: str) -> SharedMessage:
        """A lecturer's reply, added to the student's session (they see it in their chat).

        It isn't sent to the tutor agent as the student's input: the agent's view of
        what the student knows comes only from the student.
        """
        s = self._find(offering_id, share_id)
        m = Message(id=uuid.uuid4().hex, session_id=s.id, role="lecturer", content=text.strip(), created_at=self.clock())
        try:
            self.store.reply_shared(share_id, m, self.clock())
        except LookupError:
            raise NotShared('this session is no longer shared') from None
        return self._shared_message(share_id, m)

    def _shared_message(self, share_id: str, m: Message) -> SharedMessage:
        return SharedMessage(
            id=_message_id(share_id, m.id), role=m.role, content=m.content, sources=m.sources,
            knowledge_origin=m.knowledge_origin, activity=_remap(share_id, m.activity), answer_for=_message_id(share_id, m.answer_for) if m.answer_for else None, created_at=m.created_at,
        )

    def view(self, offering_id: str, share_id: str) -> SharedSessionView:
        s = self._find(offering_id, share_id)
        messages: list[Message] = self.store.messages(s.student_id, s.id)
        return SharedSessionView(
            session=self._summary(s),
            messages=[self._shared_message(share_id, m) for m in messages],
        )
