from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .models import LearningSession, Message
from .store import SessionStore
from .tutor import PlaceholderTutor, Tutor, TutorReply


class NotFound(LookupError):
    pass


def _title(goal: str) -> str:
    return goal if len(goal) <= 60 else goal[:57] + "…"


@dataclass
class SessionService:
    store: SessionStore
    tutor: Tutor = field(default_factory=PlaceholderTutor)
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def _get(self, student_id: str, session_id: str, offering_id: str) -> LearningSession:
        s = self.store.get(student_id, session_id)
        if s is None or s.offering_id != offering_id:
            raise NotFound("no such session")  # same answer for "missing" and "someone else's"
        return s

    def _save_replies(self, session: LearningSession, replies: list[TutorReply]) -> list[Message]:
        """Store the tutor's messages. A repeat of the activity already on screen isn't shown twice."""
        last_activity = next((m.activity for m in reversed(self.store.messages(session.student_id, session.id)) if m.activity), None)
        out = []
        for r in replies:
            if r.activity and last_activity and r.activity.get("activity_id") == last_activity.get("activity_id"):
                continue
            m = Message(
                id=uuid.uuid4().hex, session_id=session.id, role="tutor", content=r.content,
                sources=r.sources, knowledge_origin=r.knowledge_origin, activity=r.activity, created_at=self.clock(),
            )
            self.store.add_message(session.student_id, m)
            out.append(m)
            last_activity = r.activity or last_activity
        self.store.put(session.model_copy(update={"updated_at": self.clock()}))
        return out

    def _learner(self, session: LearningSession, content: str, answer_for: str | None = None) -> Message:
        m = Message(id=uuid.uuid4().hex, session_id=session.id, role="learner", content=content,
                    answer_for=answer_for, created_at=self.clock())
        self.store.add_message(session.student_id, m)
        return m

    def list(self, student_id: str, offering_id: str) -> list[LearningSession]:
        return self.store.list(student_id, offering_id)

    async def create(self, student_id: str, offering_id: str, goal: str) -> tuple[LearningSession, list[Message]]:
        now = self.clock()
        clean = " ".join(goal.split())
        session = LearningSession(
            id=uuid.uuid4().hex, student_id=student_id, offering_id=offering_id,
            goal=clean, title=_title(clean), created_at=now, updated_at=now,
        )
        self.store.put(session)
        try:
            replies = await self.tutor.start(session)
        except Exception:
            self.store.delete(student_id, session.id)  # no half-started sessions
            raise
        return session, self._save_replies(session, replies)

    def get(self, student_id: str, offering_id: str, session_id: str) -> tuple[LearningSession, list[Message]]:
        s = self._get(student_id, session_id, offering_id)
        return s, self.store.messages(student_id, s.id)

    def rename(self, student_id: str, offering_id: str, session_id: str, title: str) -> LearningSession:
        s = self._get(student_id, session_id, offering_id)
        updated = s.model_copy(update={"title": " ".join(title.split())[:80]})
        LearningSession.model_validate(updated.model_dump())  # reject a blank title
        self.store.put(updated)
        return updated

    def share(self, student_id: str, offering_id: str, session_id: str) -> LearningSession:
        """Share with the unit's lecturers, anonymously. A new token every time (unlinkable)."""
        s = self._get(student_id, session_id, offering_id)
        updated = s.model_copy(update={"shared": True, "shared_at": self.clock(), "share_token": uuid.uuid4().hex})
        self.store.put(updated)
        return updated

    def unshare(self, student_id: str, offering_id: str, session_id: str) -> LearningSession:
        """Stop sharing. Lecturer access ends at once: their routes look the session up by its token."""
        s = self._get(student_id, session_id, offering_id)
        updated = s.model_copy(update={"shared": False, "shared_at": None, "share_token": None})
        self.store.put(updated)
        return updated

    def delete(self, student_id: str, offering_id: str, session_id: str) -> None:
        self._get(student_id, session_id, offering_id)
        self.store.delete(student_id, session_id)

    async def send(self, student_id: str, offering_id: str, session_id: str, text: str) -> list[Message]:
        """A chat message: store it, get the tutor's reply, return both."""
        s = self._get(student_id, session_id, offering_id)
        learner = self._learner(s, text.strip())
        return [learner, *self._save_replies(s, await self.tutor.message(s, text.strip()))]

    async def answer(self, student_id: str, offering_id: str, session_id: str, question_id: str, *,
                     choice_id: str | None, text: str | None, shown: str, hint_used: bool = False) -> list[Message]:
        """An answer to the tutor's question. `shown` is how it appears in the chat (e.g. the chosen option)."""
        s = self._get(student_id, session_id, offering_id)
        replies = await self.tutor.answer(s, question_id, choice_id=choice_id, text=text, hint_used=hint_used)
        learner = self._learner(s, shown, answer_for=question_id)
        return [learner, *self._save_replies(s, replies)]

    async def continue_(self, student_id: str, offering_id: str, session_id: str, activity_id: str) -> list[Message]:
        s = self._get(student_id, session_id, offering_id)
        return self._save_replies(s, await self.tutor.continue_(s, activity_id))
