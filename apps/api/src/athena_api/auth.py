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
