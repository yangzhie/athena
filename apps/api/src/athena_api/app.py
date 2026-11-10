"""FastAPI application factory. Each module (SRS, sessions) adds its router here."""

import os
from pathlib import Path

from fastapi import FastAPI

from .spaces.service import StudySpaces
from .spaces.api import spaces_router
from .spaces.identity import AnonymousIdentity

from .auth import LecturerResolver, StudentResolver, dev_lecturer_resolver
from .env import load_dotenv
from .lectures.api import lectures_router
from .lectures.service import LectureService
from .lectures.store import SqliteLectureStore
from .sessions.agent_tutor import agent_tutor_from_env
from .sessions.api import sessions_router, shared_sessions_router
from .sessions.shared import SharedSessions
from .sessions.material import LectureMaterial
from .sessions.service import SessionService
from .sessions.store import SqliteSessionStore
from .srs.api import srs_router
from .srs.bank_admin import BankAdmin
from .srs.bank_api import bank_router
from .srs.rephrase import OpenAIRephraser, RephraseError
from .srs.service import SrsService
from .srs.store import SqliteStore


def create_app(
    *,
    srs: SrsService | None = None,
    sessions: SessionService | None = None,
    lectures: LectureService | None = None,
    resolve_student: StudentResolver | None = None,
    resolve_lecturer: LecturerResolver | None = None,
    spaces: StudySpaces | None = None,
) -> FastAPI:
    app = FastAPI(title="Athena API", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    if srs is None or sessions is None or lectures is None:
        load_dotenv()
        db = Path(os.environ.get("ATHENA_DB", "data/athena.db"))
        lectures = lectures or LectureService(SqliteLectureStore(db))
        srs = srs or SrsService(SqliteStore(db), rephraser=_rephraser())
        if sessions is None:
            tutor = agent_tutor_from_env(material=LectureMaterial(lectures))
            sessions = SessionService(SqliteSessionStore(db), tutor=tutor)

    @app.get("/tutor/status")
    def tutor_status() -> dict:
        return {"mode": getattr(sessions.tutor, "mode", "injected"),
                "available": getattr(sessions.tutor, "available", True),
                "scripted": getattr(sessions.tutor, "mode", "injected") in {"demo", "placeholder"}}

    if resolve_student is None:
        spaces = spaces or StudySpaces(Path(os.environ.get("ATHENA_DB", "data/athena.db")))
        app.add_middleware(AnonymousIdentity, spaces=spaces)

        def resolve_student(request):
            student = request.state.student_id
            offering = request.path_params.get('offering_id')
            if offering:
                spaces.environment(student, offering)
            return student

        def resolve_lecturer(request, offering):
            student = request.state.student_id
            return student if spaces.manages(student, offering) else None

        sessions.environment_resolver = spaces.environment
        app.state.spaces = spaces
        app.include_router(spaces_router(spaces))
    else:
        # Explicit host/test adapters own their authentication and offering policy.
        resolve_lecturer = resolve_lecturer or dev_lecturer_resolver

    app.include_router(srs_router(srs, resolve_student))
    app.include_router(bank_router(BankAdmin(srs.store), resolve_lecturer))
    app.include_router(sessions_router(sessions, resolve_student))
    app.include_router(shared_sessions_router(SharedSessions(sessions.store), resolve_lecturer))
    app.include_router(lectures_router(lectures, resolve_student, resolve_lecturer))
    return app


def _rephraser() -> OpenAIRephraser | None:
    """Live rephrasing when OpenAI is configured; otherwise items fall back to existing wordings."""
    try:
        return OpenAIRephraser(os.environ.get("ATHENA_REPHRASE_MODEL") or None)
    except RephraseError:
        return None
