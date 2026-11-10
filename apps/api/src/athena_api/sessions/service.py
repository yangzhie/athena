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

    def _tutor_message(self, session: LearningSession, reply: TutorReply) -> Message:
        return Message(
            id=uuid.uuid4().hex, session_id=session.id, role="tutor", content=reply.content,
            sources=reply.sources, knowledge_origin=reply.knowledge_origin, created_at=self.clock(),
        )

    def list(self, student_id: str, offering_id: str) -> list[LearningSession]:
        return self.store.list(student_id, offering_id)

    def create(self, student_id: str, offering_id: str, goal: str) -> tuple[LearningSession, list[Message]]:
        now = self.clock()
        clean = " ".join(goal.split())
        session = LearningSession(
            id=uuid.uuid4().hex, student_id=student_id, offering_id=offering_id,
            goal=clean, title=_title(clean), created_at=now, updated_at=now,
        )
        self.store.put(session)
        opening = self._tutor_message(session, self.tutor.opening(session))
        self.store.add_message(student_id, opening)
        return session, [opening]

    def get(self, student_id: str, offering_id: str, session_id: str) -> tuple[LearningSession, list[Message]]:
        s = self._get(student_id, session_id, offering_id)
        return s, self.store.messages(student_id, s.id)

    def rename(self, student_id: str, offering_id: str, session_id: str, title: str) -> LearningSession:
        s = self._get(student_id, session_id, offering_id)
        updated = s.model_copy(update={"title": " ".join(title.split())[:80]})
        LearningSession.model_validate(updated.model_dump())  # reject a blank title
        self.store.put(updated)
        return updated

    def delete(self, student_id: str, offering_id: str, session_id: str) -> None:
        self._get(student_id, session_id, offering_id)
        self.store.delete(student_id, session_id)

    def send(self, student_id: str, offering_id: str, session_id: str, text: str) -> list[Message]:
        """Store the learner's message, get the tutor's reply, return both."""
        s = self._get(student_id, session_id, offering_id)
        learner = Message(id=uuid.uuid4().hex, session_id=s.id, role="learner", content=text.strip(), created_at=self.clock())
        self.store.add_message(student_id, learner)
        reply = self._tutor_message(s, self.tutor.reply(s, self.store.messages(student_id, s.id)))
        self.store.add_message(student_id, reply)
        self.store.put(s.model_copy(update={"updated_at": self.clock()}))
        return [learner, reply]
