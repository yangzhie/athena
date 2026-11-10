"""Who is making the request. Identity always comes from the server side."""

import os
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request

StudentResolver = Callable[[Request], str | None]


def dev_student_resolver(request: Request) -> str | None:
    """PoC only: every request is the student named in ATHENA_DEV_STUDENT_ID.

    Real identity comes from university SSO via trusted middleware. Never read
    a student id from request headers, query or body.
    """
    return os.environ.get("ATHENA_DEV_STUDENT_ID") or None


def student_dependency(resolve: StudentResolver):
    """A FastAPI dependency giving the signed-in student's id, or 401."""

    def student(request: Request) -> str:
        sid = resolve(request)
        if not sid:
            raise HTTPException(401, "sign in required")
        return sid

    return Annotated[str, Depends(student)]


LecturerResolver = Callable[[Request, str], str | None]
"""(request, offering_id) → lecturer id if the caller teaches that offering, else None."""


def dev_lecturer_resolver(request: Request, offering_id: str) -> str | None:
    """PoC only: every request is the lecturer in ATHENA_DEV_LECTURER_ID, for every offering.

    Real roles come from SSO plus the offering's lecturer list. The web app's
    "Viewing as" switch only changes the UI; it grants nothing here.
    """
    return os.environ.get("ATHENA_DEV_LECTURER_ID") or None


def lecturer_dependency(resolve: LecturerResolver):
    """A FastAPI dependency giving the lecturer's id for the path's offering, or 403."""

    def lecturer(request: Request, offering_id: str) -> str:
        lid = resolve(request, offering_id)
        if not lid:
            raise HTTPException(403, "only this unit's lecturers can do that")
        return lid

    return Annotated[str, Depends(lecturer)]
