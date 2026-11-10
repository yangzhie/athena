import sqlite3
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .bridge import catalog
from .service import Playgrounds
from .tutor import PlaygroundTutor
from ..request_types import OperationId


class CommandBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    operation_id: Annotated[str, StringConstraints(min_length=8, max_length=128, pattern=r'^[a-zA-Z0-9:_-]+$')]
    revision: int = Field(ge=0)
    command: dict
    catalog_version: Literal['1.0.0']


class TurnBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: Annotated[str, StringConstraints(min_length=1, max_length=4000)]
    kind: Literal['question', 'scene', 'event', 'execution'] = 'question'


def playground_router(service: Playgrounds):
    tutor = PlaygroundTutor(service)
    service.tutor = tutor
    router = APIRouter(prefix='/units/{offering_id}/sessions/{session_id}/playground', tags=['Playground'])

    def call(fn, *args):
        try:
            return fn(*args)
        except sqlite3.Error:
            raise HTTPException(503, 'Playground storage unavailable. Retry with the same operation ID.') from None

    @router.get('/contract')
    def contract(offering_id: str, session_id: str, request: Request):
        service.authorize(request.state.student_id, offering_id, session_id)
        return catalog()

    @router.get('')
    def snapshot(offering_id: str, session_id: str, request: Request):
        return call(service.get, request.state.student_id, offering_id, session_id)

    @router.post('/commands')
    def command(offering_id: str, session_id: str, body: CommandBody, request: Request):
        return call(service.command, request.state.student_id, offering_id, session_id,
                    body.operation_id, body.revision, body.command)

    @router.get('/executions')
    def executions(offering_id: str, session_id: str, request: Request):
        student = request.state.student_id
        service.authorize(student, offering_id, session_id)
        return service.executions.list(student, session_id)

    @router.delete('/executions/{execution_id}', status_code=204)
    def cancel(offering_id: str, session_id: str, execution_id: str, request: Request):
        student = request.state.student_id
        service.authorize(student, offering_id, session_id)
        call(service.executions.cancel, student, session_id, execution_id)

    @router.post('/executions/{execution_id}/interpret')
    async def interpret(offering_id: str, session_id: str, execution_id: str, request: Request):
        student = request.state.student_id
        service.authorize(student, offering_id, session_id)
        with service.lock:
            job = service.db.execute('SELECT * FROM executions WHERE id=? AND student=? AND session=?', (execution_id, student, session_id)).fetchone()
        if not job:
            raise HTTPException(404, 'Execution not found')
        if job['state'] != 'finished':
            raise HTTPException(409, 'Only completed verified executions can be interpreted')
        return await tutor.turn(student, offering_id, session_id, 'execution:' + execution_id,
                                'Interpret verified execution ' + execution_id + ' and ask an independent reasoning question.', 'execution')

    @router.post('/turns')
    async def turn(offering_id: str, session_id: str, body: TurnBody, request: Request, operation_id: OperationId = None):
        if not operation_id:
            raise HTTPException(422, 'Idempotency-Key is required')
        return await tutor.turn(request.state.student_id, offering_id, session_id, operation_id, body.text, body.kind)

    @router.post('/turns/{operation_id}/retry')
    async def retry(offering_id: str, session_id: str, operation_id: str, request: Request):
        student = request.state.student_id
        service.authorize(student, offering_id, session_id)
        with service.lock:
            row = service.db.execute('SELECT request FROM playground_turns WHERE session=? AND operation=?', (session_id, operation_id)).fetchone()
        if not row:
            raise HTTPException(404, 'Tutor operation not found')
        import json
        saved = json.loads(row['request'])
        return await tutor.turn(student, offering_id, session_id, operation_id, saved['text'], saved['kind'])

    @router.post('/replacements/{proposal_id}/{decision}')
    def replace(offering_id: str, session_id: str, proposal_id: str, decision: Literal['accept', 'reject'], body: CommandBody, request: Request):
        student = request.state.student_id
        service.authorize(student, offering_id, session_id)
        import json
        with service.lock:
            row = service.db.execute('SELECT * FROM playground_replacements WHERE id=? AND session=?', (proposal_id, session_id)).fetchone()
            if not row or row['status'] not in ('pending', decision):
                raise HTTPException(409, 'Replacement is no longer pending')
            if decision == 'accept':
                result = service.command(student, offering_id, session_id, body.operation_id, body.revision,
                                         {'kind': 'replace_confirmed', 'scene': json.loads(row['scene'])}, trusted=True)
            else:
                result = service.get(student, offering_id, session_id)
            with service.db:
                service.db.execute('UPDATE playground_replacements SET status=? WHERE id=?', (decision, proposal_id))
            return result

    return router
