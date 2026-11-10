"""FastAPI application factory. Modules (SRS first) add their routers here."""

import os
from pathlib import Path

from fastapi import FastAPI, Request

from .env import load_dotenv
from .srs.api import StudentResolver, srs_router
from .srs.rephrase import OpenAIRephraser, RephraseError
from .srs.service import SrsService
from .srs.store import SqliteStore, SrsStore


def dev_student_resolver(request: Request) -> str | None:
    """PoC only: every request is the student named in ATHENA_DEV_STUDENT_ID.

    Real identity comes from university SSO via trusted middleware. Never read
    a student id from request headers, query or body.
    """
    return os.environ.get("ATHENA_DEV_STUDENT_ID") or None


def create_app(
    *,
    srs: SrsService | None = None,
    resolve_student: StudentResolver = dev_student_resolver,
) -> FastAPI:
    app = FastAPI(title="Athena API", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    if srs is None:
        load_dotenv()
        store: SrsStore = SqliteStore(Path(os.environ.get("ATHENA_DB", "data/athena.db")))
        srs = SrsService(store, rephraser=_rephraser())
    app.include_router(srs_router(srs, resolve_student))
    return app


def _rephraser() -> OpenAIRephraser | None:
    """Live rephrasing when OpenAI is configured; otherwise items fall back to existing wordings."""
    try:
        return OpenAIRephraser(os.environ.get("ATHENA_REPHRASE_MODEL") or None)
    except RephraseError:
        return None
