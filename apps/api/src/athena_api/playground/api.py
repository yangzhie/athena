import sqlite3
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .bridge import catalog
from .service import Playgrounds


class CommandBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    operation_id: Annotated[str, StringConstraints(min_length=8, max_length=128, pattern=r'^[a-zA-Z0-9:_-]+$')]
    revision: int = Field(ge=0)
    command: dict
    catalog_version: Literal['1.0.0']


def playground_router(service: Playgrounds):
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

    return router
