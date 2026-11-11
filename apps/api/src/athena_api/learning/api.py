from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .service import PUBLIC_CONCEPTS, key, normalise


class TopicBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=160, pattern=r'\S')
    concept_id: str | None = None


def learning_router(memory):
    router = APIRouter(tags=['learning memory'])
    spaces = memory.spaces

    @router.get('/learner/profile')
    def profile(request: Request):
        return memory.profile(request.state.student_id)

    @router.get('/concepts/catalogue')
    def catalogue():
        return [dict(id=id, name=names[0].title()) for id, names in PUBLIC_CONCEPTS.items()]

    @router.get('/units/{offering_id}/progress')
    def progress(offering_id: str, request: Request):
        spaces.environment(request.state.student_id, offering_id)
        return memory.profile(request.state.student_id, offering_id)

    @router.get('/units/{offering_id}/progress/evidence')
    def evidence(offering_id: str, request: Request):
        student = request.state.student_id
        spaces.environment(student, offering_id)
        with memory.lock:
            return [dict(id=r[0], session_id=r[1], concept_id=r[2], assessment_id=r[3], outcome=r[4]) for r in memory.db.execute(
                'SELECT id,session_id,concept_id,assessment_id,outcome FROM learner_evidence WHERE student_id=? AND offering_id=? ORDER BY created_at,id', (student, offering_id))]

    @router.get('/units/{offering_id}/insights')
    def insights(offering_id: str, request: Request):
        spaces.require_manager(request.state.student_id, offering_id)
        return memory.aggregates(offering_id)

    @router.get('/units/{offering_id}/topics')
    def topics(offering_id: str):
        with memory.lock:
            return [dict(id=r[0], title=r[1], concept_id=r[2]) for r in memory.db.execute(
                'SELECT id,title,concept_id FROM offering_topics WHERE offering_id=? ORDER BY title', (offering_id,))]

    @router.post('/units/{offering_id}/topics', status_code=201)
    def topic(offering_id: str, body: TopicBody, request: Request):
        spaces.require_manager(request.state.student_id, offering_id)
        title = body.title.strip()
        id = key(offering_id, normalise(title))
        canonical = body.concept_id or 'course:' + id
        with memory.lock, memory.db:
            if body.concept_id:
                if canonical not in PUBLIC_CONCEPTS and canonical != 'course:' + id:
                    raise HTTPException(422, 'Choose a canonical Concept from the catalogue or create a course Concept.')
            else:
                memory.db.execute('INSERT OR IGNORE INTO concepts VALUES (?,?,1)', (canonical, title))
            existing = memory.db.execute('SELECT concept_id FROM offering_topics WHERE offering_id=? AND id=?', (offering_id, id)).fetchone()
            if existing and existing[0] != canonical:
                raise HTTPException(409, 'This Topic already maps to a different Concept; existing evidence is not relabelled automatically.')
            memory.db.execute('INSERT OR IGNORE INTO offering_topics VALUES (?,?,?,?)', (offering_id, id, title, canonical))
        return dict(id=id, title=title, concept_id=canonical)

    return router
