"""HTTP routes for learning sessions. Scoped to the signed-in student throughout."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError

from ..auth import LecturerResolver, StudentResolver, lecturer_dependency, student_dependency
from .models import LearningSessionOut, Message, SharedMessage, SharedSessionSummary, SharedSessionView
from .service import NotFound, SessionService
from .shared import NotShared, SharedSessions
from .tutor import TutorError

from ..request_types import OperationId

Text = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]


class CreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal: Annotated[str, StringConstraints(min_length=1, max_length=200, pattern=r"\S")]


class RenameBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Annotated[str, StringConstraints(min_length=1, max_length=80, pattern=r"\S")]


class MessageBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: Annotated[str, StringConstraints(min_length=1, max_length=4000, pattern=r"\S")]


class AnswerBody(BaseModel):
    """Exactly one of choice_id (multiple choice) or text (open-ended)."""

    model_config = ConfigDict(extra="forbid")
    question_id: Text
    choice_id: str | None = None
    text: Annotated[str, StringConstraints(max_length=4000)] | None = None
    #: How the answer appears in the chat, e.g. the chosen option's text.
    shown: Annotated[str, StringConstraints(min_length=1, max_length=4000, pattern=r"\S")]
    hint_used: bool = False


class ContinueBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    activity_id: Text


class SessionWithMessages(BaseModel):
    session: LearningSessionOut
    messages: list[Message]


def sessions_router(service: SessionService, resolve_student: StudentResolver) -> APIRouter:
    router = APIRouter(prefix="/units/{offering_id}/sessions", tags=["sessions"])
    Student = student_dependency(resolve_student)

    def run(fn, *args):
        try:
            return fn(*args)
        except sqlite3.Error:
            raise HTTPException(503, "Session storage is unavailable. Retry the same submission.") from None
        except NotFound as e:
            raise HTTPException(404, str(e)) from None
        except ValidationError:
            raise HTTPException(422, "invalid value") from None

    async def arun(fn, *args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except sqlite3.Error:
            raise HTTPException(503, "Session storage is unavailable. Retry the same submission.") from None
        except NotFound as e:
            raise HTTPException(404, str(e)) from None
        except TutorError as e:
            raise HTTPException(e.status, str(e)) from None

    @router.get("", response_model=list[LearningSessionOut])
    def list_sessions(offering_id: str, sid: Student):
        return [LearningSessionOut.of(s) for s in service.list(sid, offering_id)]

    @router.post("", response_model=SessionWithMessages, status_code=201)
    async def create(offering_id: str, body: CreateBody, sid: Student, operation_id: OperationId = None):
        session, messages = await arun(service.create, sid, offering_id, body.goal, operation_id)
        return SessionWithMessages(session=LearningSessionOut.of(session), messages=messages)

    @router.post("/operations/{operation_id}/retry", response_model=SessionWithMessages)
    async def recover(offering_id: str, operation_id: str, sid: Student):
        session, messages = await arun(service.recover, sid, offering_id, operation_id)
        return SessionWithMessages(session=LearningSessionOut.of(session), messages=messages)

    @router.get("/{session_id}", response_model=SessionWithMessages)
    def get(offering_id: str, session_id: str, sid: Student):
        session, messages = run(service.get, sid, offering_id, session_id)
        return SessionWithMessages(session=LearningSessionOut.of(session), messages=messages)

    @router.patch("/{session_id}", response_model=LearningSessionOut)
    def rename(offering_id: str, session_id: str, body: RenameBody, sid: Student):
        return LearningSessionOut.of(run(service.rename, sid, offering_id, session_id, body.title))

    @router.post("/{session_id}/share", response_model=LearningSessionOut)
    def share(offering_id: str, session_id: str, sid: Student):
        """Share this session, anonymously, with the unit's lecturers."""
        return LearningSessionOut.of(run(service.share, sid, offering_id, session_id))

    @router.delete("/{session_id}/share", response_model=LearningSessionOut)
    def unshare(offering_id: str, session_id: str, sid: Student):
        """Stop sharing; lecturers lose access immediately."""
        return LearningSessionOut.of(run(service.unshare, sid, offering_id, session_id))

    @router.delete("/{session_id}", status_code=204)
    def delete(offering_id: str, session_id: str, sid: Student):
        run(service.delete, sid, offering_id, session_id)
        return Response(status_code=204)

    @router.post("/{session_id}/messages", response_model=list[Message])
    async def send(offering_id: str, session_id: str, body: MessageBody, sid: Student, operation_id: OperationId = None):
        return await arun(service.send, sid, offering_id, session_id, body.text, operation_id)

    @router.post("/{session_id}/answers", response_model=list[Message])
    async def answer(offering_id: str, session_id: str, body: AnswerBody, sid: Student):
        if (body.choice_id is None) == (body.text is None):
            raise HTTPException(422, "give exactly one of choice_id or text")
        return await arun(
            service.answer, sid, offering_id, session_id, body.question_id,
            choice_id=body.choice_id, text=body.text, shown=body.shown, hint_used=body.hint_used,
        )

    @router.post("/{session_id}/continue", response_model=list[Message])
    async def continue_(offering_id: str, session_id: str, body: ContinueBody, sid: Student):
        return await arun(service.continue_, sid, offering_id, session_id, body.activity_id)

    return router


def shared_sessions_router(shared: SharedSessions, resolve_lecturer: LecturerResolver) -> APIRouter:
    """Lecturers: sessions students have shared, anonymously (AGENTS.md, Privacy rule 6)."""
    router = APIRouter(prefix="/units/{offering_id}/shared-sessions", tags=["shared-sessions"])
    Lecturer = lecturer_dependency(resolve_lecturer)

    @router.get("", response_model=list[SharedSessionSummary])
    def list_shared(offering_id: str, _: Lecturer):
        return shared.list(offering_id)

    @router.get("/{share_id}", response_model=SharedSessionView)
    def view(offering_id: str, share_id: str, _: Lecturer):
        try:
            return shared.view(offering_id, share_id)
        except NotShared as e:
            raise HTTPException(404, str(e)) from None

    @router.post("/{share_id}/messages", response_model=SharedMessage, status_code=201)
    def reply(offering_id: str, share_id: str, body: MessageBody, _: Lecturer):
        """Reply in the thread. Only while the student keeps sharing."""
        try:
            return shared.reply(offering_id, share_id, body.text)
        except NotShared as e:
            raise HTTPException(404, str(e)) from None

    return router
