from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

from .service import CreateOffering, StudySpaces


class IdentityOut(BaseModel):
    anonymous: bool = True
    role: Literal['student', 'lecturer']


class LecturerInviteBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: str = Field(min_length=32, max_length=128)


def spaces_router(spaces: StudySpaces):
    router = APIRouter(tags=['study spaces'])

    @router.get('/identity', response_model=IdentityOut)
    def identity(request: Request):
        return IdentityOut(role='lecturer' if spaces.is_lecturer(request.state.student_id) else 'student')

    @router.post('/identity/lecturer-access', response_model=IdentityOut)
    def lecturer_access(body: LecturerInviteBody, request: Request):
        spaces.redeem_lecturer_invite(request.state.student_id, body.code)
        return identity(request)

    @router.get('/offerings')
    def offerings(request: Request):
        return spaces.list(request.state.student_id)

    @router.post('/offerings', status_code=201)
    def create(body: CreateOffering, request: Request):
        return spaces.create(request.state.student_id, body)

    @router.get('/offerings/{offering_id}')
    def get(offering_id: str, request: Request):
        return spaces.get(request.state.student_id, offering_id)

    @router.post('/offerings/{offering_id}/publish')
    def publish(offering_id: str, request: Request):
        return spaces.publish(request.state.student_id, offering_id)

    @router.delete('/offerings/{offering_id}', status_code=204)
    def delete(offering_id: str, request: Request):
        spaces.delete(request.state.student_id, offering_id)
        return Response(status_code=204)

    return router
