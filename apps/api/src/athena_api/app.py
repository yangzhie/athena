"""FastAPI application factory. Each module (SRS, sessions) adds its router here."""

import os
import asyncio
import logging
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .operations import OperationalLimits
from .privacy.lifecycle import Lifecycle
from .playground.service import Playgrounds
from .playground.api import playground_router
from .learning.service import LearningMemory
from .learning.api import learning_router
from .materials.store import Materials
from .materials.api import materials_router
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
from .sessions.material import LectureMaterial, OfferingMaterial
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
    @asynccontextmanager
    async def lifespan(app):
        async def retain():
            while True:
                lifecycle = getattr(app.state, 'lifecycle', None)
                if lifecycle:
                    try:
                        await asyncio.to_thread(lifecycle.sweep)
                        app.state.retention_available = True
                    except Exception:
                        app.state.retention_available = False
                        logging.getLogger('athena.privacy').error('Private-content cleanup unavailable; pending cleanup remains recoverable')
                await asyncio.sleep(60)
        task = asyncio.create_task(retain())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    request_logger = logging.getLogger('athena.requests')
    if not request_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(levelname)s %(name)s %(message)s'))
        request_logger.addHandler(handler)
    request_logger.setLevel(logging.INFO)

    app = FastAPI(title="Athena API", version="0.1.0", lifespan=lifespan)

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

    app.state.sessions = sessions
    app.state.srs = srs
    app.state.lectures = lectures

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

        playgrounds = Playgrounds(spaces, sessions)
        app.state.playgrounds = playgrounds
        app.include_router(playground_router(playgrounds))
        sessions.environment_resolver = spaces.environment
        app.state.spaces = spaces
        app.include_router(spaces_router(spaces))
        materials = Materials(spaces, os.environ.get('ATHENA_MATERIAL_ROOT', str(spaces.path.parent / 'materials')))
        if getattr(sessions.tutor, 'mode', None) == 'ai':
            sessions.tutor.material = OfferingMaterial(materials, lectures)
        app.state.materials = materials
        app.include_router(materials_router(materials))
        memory = LearningMemory(spaces, sessions.tutor)
        app.state.learning = memory
        lifecycle = Lifecycle(spaces, sessions, memory)
        app.state.lifecycle = lifecycle
        sessions.cleanup = lifecycle.delete
        sessions.unavailable = lifecycle.unavailable
        sessions.evidence_sink = memory.sync
        srs.private_items = memory.practice_items
        srs.private_item_writer = memory.save_practice
        srs.practice_sink = memory.practice_event
        if getattr(sessions.tutor, 'mode', None) == 'ai':
            sessions.tutor.profile_provider = memory.profile
        app.include_router(learning_router(memory))
    else:
        # Explicit host/test adapters own their authentication and offering policy.
        resolve_lecturer = resolve_lecturer or dev_lecturer_resolver

    app.add_middleware(OperationalLimits)

    @app.get("/ready")
    def readiness():
        from .playground.bridge import BUNDLE
        ai = getattr(sessions.tutor, "mode", "injected")
        statuses = {}
        if hasattr(app.state, 'spaces'):
            with app.state.spaces.lock:
                statuses = {r[0]: time.time() - r[1] < 60 for r in app.state.spaces.db.execute('SELECT kind,updated FROM worker_status')}
                if app.state.spaces.db.execute("SELECT 1 FROM material_jobs WHERE status='processing' AND lease_until>?", (time.time(),)).fetchone():
                    statuses['indexing'] = True
        result = {"ready": ai == "ai" and BUNDLE.exists() and getattr(app.state, "retention_available", True) and statuses.get('execution', False) and statuses.get('indexing', False),
                "tutor_mode": ai, "playground_engine": BUNDLE.exists(),
                "retention": getattr(app.state, "retention_available", None),
                "workers": {name: statuses.get(name, False) for name in ('execution', 'indexing')}}
        return JSONResponse(result, status_code=200 if result["ready"] else 503)


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
