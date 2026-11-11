from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .models import AnswerReceipt, LearningSession, Message
from .operations import Operation
from .store import SessionStore
from .tutor import Tutor, TutorError, UnavailableTutor


class NotFound(LookupError):
    pass


def _title(goal: str) -> str:
    return goal if len(goal) <= 60 else goal[:57] + "…"


@dataclass
class SessionService:
    store: SessionStore
    tutor: Tutor = field(default_factory=lambda: UnavailableTutor("No tutor was configured."))
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    environment_resolver: Callable[[str, str], str] | None = None
    evidence_sink: Callable | None = None
    cleanup: Callable | None = None
    unavailable: Callable[[str], bool] | None = None

    def _get(self, student_id: str, session_id: str, offering_id: str) -> LearningSession:
        s = self.store.get(student_id, session_id)
        if s is None or s.offering_id != offering_id or (self.unavailable and self.unavailable(session_id)):
            raise NotFound("no such session")  # same answer for "missing" and "someone else's"
        return s

    async def _operate(self, operation: Operation) -> Operation:
        try:
            operation = self.store.begin_operation(operation)
        except LookupError:
            raise NotFound("no such session") from None
        if operation.complete:
            if self.evidence_sink:
                self.evidence_sink(operation)
            return operation
        s = operation.session
        try:
            if hasattr(self.tutor, "operation"):
                replies = await self.tutor.operation(operation)
            elif operation.kind == "start":
                replies = await self.tutor.start(s)
            elif operation.kind == "message":
                replies = await self.tutor.message(s, **operation.payload)
            elif operation.kind == "answer":
                replies = await self.tutor.answer(s, **operation.payload)
            else:
                replies = await self.tutor.continue_(s, **operation.payload)
        except TutorError as error:
            if error.status in {400, 413, 422}:
                self.store.fail_operation(operation, str(error))
            raise
        messages = []
        if operation.shown is not None:
            messages.append(Message(id=uuid.uuid4().hex, session_id=s.id, role="learner",
                                    content=operation.shown, answer_for=operation.payload.get("question_id"), created_at=self.clock()))
        last_activity = next((m.activity for m in reversed(self.store.messages(s.student_id, s.id)) if m.activity), None)
        for r in replies:
            if r.activity and last_activity and r.activity.get("activity_id") == last_activity.get("activity_id"):
                continue
            messages.append(Message(id=uuid.uuid4().hex, session_id=s.id, role="tutor", content=r.content,
                                    sources=r.sources, knowledge_origin=r.knowledge_origin, activity=r.activity, created_at=self.clock()))
            last_activity = r.activity or last_activity
        operation.messages = messages
        try:
            complete = self.store.complete_operation(operation, self.clock())
            if self.evidence_sink:
                self.evidence_sink(complete)
            return complete
        except LookupError:
            raise NotFound("no such session") from None

    def list(self, student_id: str, offering_id: str) -> list[LearningSession]:
        return [s for s in self.store.list(student_id, offering_id) if not self.unavailable or not self.unavailable(s.id)]

    async def create(self, student_id: str, offering_id: str, goal: str, operation_id: str | None = None) -> tuple[LearningSession, list[Message]]:
        now = self.clock()
        clean = " ".join(goal.split())
        session = LearningSession(
            id=uuid.uuid4().hex, student_id=student_id, offering_id=offering_id,
            goal=clean, title=_title(clean),
            environment_id=self.environment_resolver(student_id, offering_id) if self.environment_resolver else None, created_at=now, updated_at=now,
        )
        operation_id = "start:" + (operation_id or uuid.uuid4().hex)
        previous = self.store.operation(student_id, offering_id, operation_id)
        if previous:
            session = previous.session
        operation = await self._operate(Operation(id=operation_id, kind="start", session=session, payload={"goal": clean}))
        return operation.session, operation.messages

    async def recover(self, student_id: str, offering_id: str, operation_id: str) -> tuple[LearningSession, list[Message]]:
        operation = self.store.operation(student_id, offering_id, operation_id)
        if operation is None:
            raise NotFound("no such operation")
        if operation.kind != "start" or operation.complete:
            self._get(student_id, operation.session.id, offering_id)
        operation = await self._operate(operation)
        return operation.session, operation.messages

    def get(self, student_id: str, offering_id: str, session_id: str) -> tuple[LearningSession, list[Message]]:
        s = self._get(student_id, session_id, offering_id)
        return s, self.store.messages(student_id, s.id)

    def rename(self, student_id: str, offering_id: str, session_id: str, title: str) -> LearningSession:
        s = self._get(student_id, session_id, offering_id)
        updated = s.model_copy(update={"title": " ".join(title.split())[:80]})
        LearningSession.model_validate(updated.model_dump())  # reject a blank title
        try:
            updated = self.store.update_existing(updated, {'title'})
        except LookupError:
            raise NotFound('no such session') from None
        return updated

    def share(self, student_id: str, offering_id: str, session_id: str) -> LearningSession:
        """Share with the unit's lecturers, anonymously. A new token every time (unlinkable)."""
        s = self._get(student_id, session_id, offering_id)
        updated = s.model_copy(update={"shared": True, "shared_at": self.clock(), "share_token": uuid.uuid4().hex})
        try:
            updated = self.store.update_existing(updated, {'shared', 'shared_at', 'share_token'})
        except LookupError:
            raise NotFound('no such session') from None
        return updated

    def unshare(self, student_id: str, offering_id: str, session_id: str) -> LearningSession:
        """Stop sharing. Lecturer access ends at once: their routes look the session up by its token."""
        s = self._get(student_id, session_id, offering_id)
        updated = s.model_copy(update={"shared": False, "shared_at": None, "share_token": None})
        try:
            updated = self.store.update_existing(updated, {'shared', 'shared_at', 'share_token'})
        except LookupError:
            raise NotFound('no such session') from None
        return updated

    def delete(self, student_id: str, offering_id: str, session_id: str) -> None:
        if self.cleanup:
            return self.cleanup(student_id, offering_id, session_id)
        self._get(student_id, session_id, offering_id)
        self.store.delete(student_id, session_id)

    async def send(self, student_id: str, offering_id: str, session_id: str, text: str,
                   operation_id: str | None = None) -> list[Message]:
        s = self._get(student_id, session_id, offering_id)
        operation = await self._operate(Operation(id="message:" + (operation_id or uuid.uuid4().hex), kind="message",
                                                 session=s, payload={"text": text.strip()}, shown=text.strip()))
        return operation.messages

    async def answer(self, student_id: str, offering_id: str, session_id: str, question_id: str, *,
                     choice_id: str | None, text: str | None, shown: str, hint_used: bool = False) -> list[Message]:
        """An answer to the tutor's question. `shown` is how it appears in the chat (e.g. the chosen option)."""
        s = self._get(student_id, session_id, offering_id)
        submitted = AnswerReceipt(question_id=question_id, choice_id=choice_id,
                                  text=text.strip() if text is not None else None, hint_used=hint_used)
        # Read history before the receipt so a concurrently completed exchange
        # cannot be mistaken for a legacy answer without retry metadata.
        answered = any(m.answer_for == question_id for m in self.store.messages(student_id, session_id))
        previous = self.store.answer_receipt(student_id, session_id, question_id)
        if previous is not None:
            if not previous.same_submission(submitted):
                raise TutorError("This question already has an answer; request a fresh question.", 409)
            if self.evidence_sink:
                operation = self.store.operation(student_id, offering_id, 'answer:' + question_id)
                self.evidence_sink(operation or Operation(id='answer:' + question_id, kind='answer', session=s,
                                                        payload=submitted.model_dump(exclude={'messages'}), complete=True))
            return previous.messages
        if answered:
            # Pre-receipt chats don't retain the submitted choice/hint metadata.
            # Never guess that a new submission matches one of those answers.
            raise TutorError("This question was answered before retry support was available. Refresh the session.", 409)
        operation = await self._operate(Operation(id="answer:" + question_id, kind="answer", session=s,
                                                 payload=submitted.model_dump(exclude={"messages"}), shown=shown))
        return operation.messages

    async def continue_(self, student_id: str, offering_id: str, session_id: str, activity_id: str) -> list[Message]:
        s = self._get(student_id, session_id, offering_id)
        operation = await self._operate(Operation(id="continue:" + activity_id, kind="continue", session=s,
                                                 payload={"activity_id": activity_id}))
        return operation.messages
