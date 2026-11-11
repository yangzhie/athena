"""HTTP routes for SRS. Student identity always comes from the server-side resolver."""

import sqlite3
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from ..request_types import OperationId
from ..auth import StudentResolver, student_dependency

from .scheduler import ReviewError
from .service import Conflict, NotFound, SrsService

class AnswerBody(BaseModel):
    """No student id here: identity comes from authentication, never the request body."""

    model_config = ConfigDict(extra="forbid")
    item_id: str
    variant_id: str
    answer: int | float | str | None = None


class RatingBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rating: Literal["again", "hard", "good", "easy"]


class Summary(BaseModel):
    total_items: int
    due_now: int
    new_available: int
    reviewed_today: int
    next_due_at: datetime | None


def srs_router(service: SrsService, resolve_student: StudentResolver) -> APIRouter:
    router = APIRouter(prefix="/units/{offering_id}/srs", tags=["srs"])

    Student = student_dependency(resolve_student)

    def run(fn, *args):
        try:
            return fn(*args)
        except sqlite3.Error:
            raise HTTPException(503, 'Practice storage is unavailable. Retry the same submission.') from None
        except NotFound as e:
            raise HTTPException(404, str(e)) from None
        except Conflict as e:
            raise HTTPException(409, str(e)) from None
        except ReviewError as e:
            raise HTTPException(400, str(e)) from None

    @router.get("/summary", response_model=Summary)
    def summary(offering_id: str, sid: Student):
        return run(service.summary, sid, offering_id)

    @router.get("/next")
    def next_question(offering_id: str, sid: Student):
        return run(service.next, sid, offering_id)

    @router.post('/operations/{operation_id}/retry')
    def recover(offering_id: str, operation_id: str, sid: Student):
        return run(service.recover, sid, offering_id, operation_id)

    @router.get('/pending')
    def pending(offering_id: str, sid: Student):
        return run(service.pending, sid, offering_id)

    @router.post("/attempts")
    def answer(offering_id: str, body: AnswerBody, sid: Student, operation_id: OperationId = None):
        return run(service.answer, sid, offering_id, body.item_id, body.variant_id, body.answer, operation_id)

    @router.post("/attempts/{attempt_id}/rating")
    def rate(offering_id: str, attempt_id: str, body: RatingBody, sid: Student, operation_id: OperationId = None):
        return run(service.rate, sid, offering_id, attempt_id, body.rating, operation_id)

    return router
