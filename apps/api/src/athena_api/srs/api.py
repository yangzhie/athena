"""HTTP routes for SRS. Student identity always comes from the server-side resolver."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from .scheduler import ReviewError
from .service import Conflict, NotFound, SrsService

StudentResolver = Callable[[Request], str | None]


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

    def student(request: Request) -> str:
        sid = resolve_student(request)
        if not sid:
            raise HTTPException(401, "sign in required")
        return sid

    Student = Annotated[str, Depends(student)]

    def run(fn, *args):
        try:
            return fn(*args)
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

    @router.post("/attempts")
    def answer(offering_id: str, body: AnswerBody, sid: Student):
        return run(service.answer, sid, offering_id, body.item_id, body.variant_id, body.answer)

    @router.post("/attempts/{attempt_id}/rating")
    def rate(offering_id: str, attempt_id: str, body: RatingBody, sid: Student):
        return run(service.rate, sid, offering_id, attempt_id, body.rating)

    return router
