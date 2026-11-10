"""Lecture routes. Students: approved clips, no transcripts. Lecturers: review."""

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..auth import LecturerResolver, StudentResolver, lecturer_dependency, student_dependency
from .models import LecturerLecture, StudentLecture
from .service import Invalid, LectureService, NotFound


class StatusBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["pending", "approved", "rejected"]


class EditBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    start_s: Annotated[float, Field(ge=0)]
    end_s: Annotated[float, Field(ge=0)]


def lectures_router(service: LectureService, resolve_student: StudentResolver, resolve_lecturer: LecturerResolver) -> APIRouter:
    router = APIRouter(prefix="/units/{offering_id}/lectures", tags=["lectures"])
    Student = student_dependency(resolve_student)
    Lecturer = lecturer_dependency(resolve_lecturer)

    def run(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except NotFound as e:
            raise HTTPException(404, str(e)) from None
        except Invalid as e:
            raise HTTPException(422, str(e)) from None

    @router.get("", response_model=list[StudentLecture])
    def for_students(offering_id: str, _: Student):
        return service.for_students(offering_id)

    @router.get("/review", response_model=list[LecturerLecture])
    def for_lecturers(offering_id: str, _: Lecturer):
        return service.for_lecturers(offering_id)

    clip = "/{lecture_id}/clips/{clip_id}"

    @router.post(f"{clip}/status", status_code=204)
    def set_status(offering_id: str, lecture_id: str, clip_id: str, body: StatusBody, _: Lecturer):
        run(service.set_status, offering_id, lecture_id, clip_id, body.status)

    @router.patch(clip, status_code=204)
    def edit(offering_id: str, lecture_id: str, clip_id: str, body: EditBody, _: Lecturer):
        run(service.edit, offering_id, lecture_id, clip_id, title=body.title, start_s=body.start_s, end_s=body.end_s)

    @router.delete(f"{clip}/review", status_code=204)
    def reset(offering_id: str, lecture_id: str, clip_id: str, _: Lecturer):
        run(service.reset, offering_id, lecture_id, clip_id)

    @router.post("/{lecture_id}/approve-pending")
    def approve_pending(offering_id: str, lecture_id: str, _: Lecturer):
        return {"approved": run(service.approve_pending, offering_id, lecture_id)}

    return router
