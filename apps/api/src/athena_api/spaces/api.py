from fastapi import APIRouter, Request, Response

from .service import CreateOffering, StudySpaces


def spaces_router(spaces: StudySpaces):
    router = APIRouter(tags=['study spaces'])

    @router.get('/identity')
    def identity():
        return {'anonymous': True}

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
