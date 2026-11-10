"""Lecturer side of shared sessions (AGENTS.md, Privacy rule 6).

Lecturers find a shared session only by its share token, which is new on every
share and cleared when the student stops sharing, so access ends immediately and
separate shares can't be linked. Nothing returned identifies the student: no
student id, no session id.
"""

import hashlib
from dataclasses import dataclass

from .models import LearningSession, Message, SharedMessage, SharedSessionSummary, SharedSessionView
from .store import SessionStore


class NotShared(LookupError):
    pass


def _message_id(token: str, message_id: str) -> str:
    """Per-share message ids, so ids don't carry over between shares."""
    return hashlib.sha256(f"{token}:{message_id}".encode()).hexdigest()[:16]


@dataclass
class SharedSessions:
    store: SessionStore

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

    def view(self, offering_id: str, share_id: str) -> SharedSessionView:
        s = self._find(offering_id, share_id)
        messages: list[Message] = self.store.messages(s.student_id, s.id)
        return SharedSessionView(
            session=self._summary(s),
            messages=[
                SharedMessage(
                    id=_message_id(share_id, m.id), role=m.role, content=m.content, sources=m.sources,
                    knowledge_origin=m.knowledge_origin, activity=m.activity, answer_for=m.answer_for,
                    created_at=m.created_at,
                )
                for m in messages
            ],
        )
