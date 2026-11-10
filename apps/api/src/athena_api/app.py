"""FastAPI application factory. Each module (SRS, sessions) adds its router here."""

import os
from pathlib import Path

from fastapi import FastAPI

from .auth import StudentResolver, dev_student_resolver
from .env import load_dotenv
from .sessions.agent_tutor import agent_tutor_from_env
from .sessions.api import sessions_router
from .sessions.service import SessionService
from .sessions.tutor import PlaceholderTutor
from .sessions.store import SqliteSessionStore
from .srs.api import srs_router
from .srs.rephrase import OpenAIRephraser, RephraseError
from .srs.service import SrsService
from .srs.store import SqliteStore


def create_app(
    *,
    srs: SrsService | None = None,
    sessions: SessionService | None = None,
    resolve_student: StudentResolver = dev_student_resolver,
) -> FastAPI:
    app = FastAPI(title="Athena API", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    if srs is None or sessions is None:
        load_dotenv()
        db = Path(os.environ.get("ATHENA_DB", "data/athena.db"))
        srs = srs or SrsService(SqliteStore(db), rephraser=_rephraser())
        sessions = sessions or SessionService(SqliteSessionStore(db), tutor=agent_tutor_from_env() or PlaceholderTutor())
    app.include_router(srs_router(srs, resolve_student))
    app.include_router(sessions_router(sessions, resolve_student))
    return app


def _rephraser() -> OpenAIRephraser | None:
    """Live rephrasing when OpenAI is configured; otherwise items fall back to existing wordings."""
    try:
        return OpenAIRephraser(os.environ.get("ATHENA_REPHRASE_MODEL") or None)
    except RephraseError:
        return None
