import os
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

from .extract import ExtractionError, validate
from .store import Materials


def materials_router(materials: Materials):
    router = APIRouter(prefix='/units/{offering_id}/materials', tags=['materials'])
    spaces = materials.spaces

    def manager(request, offering):
        spaces.require_manager(request.state.student_id, offering)

    def visible(request, offering, id):
        row = materials.get(offering, id)
        if not spaces.manages(request.state.student_id, offering) and not (row['published'] and row['status'] == 'ready'):
            raise HTTPException(404, 'Material not found or not published.')
        return row

    @router.get('')
    def list_materials(offering_id: str, request: Request):
        return materials.list(offering_id, manager=spaces.manages(request.state.student_id, offering_id))

    @router.post('', status_code=202)
    async def upload(offering_id: str, request: Request, filename: str = Query(min_length=1, max_length=240), replace: str | None = None):
        manager(request, offering_id)
        row = materials.reserve_upload(offering_id, filename, replace)
        limit = int(os.environ.get('ATHENA_RECORDING_MAX_BYTES' if row['kind'] == 'recording' else 'ATHENA_DOCUMENT_MAX_BYTES',
                                   str(500 * 1024 * 1024 if row['kind'] == 'recording' else 50 * 1024 * 1024)))
        size = 0
        path = Path(row['storage_path'])
        try:
            with path.open('xb') as stream:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > limit:
                        raise HTTPException(413, 'The file exceeds the configured upload limit.')
                    stream.write(chunk)
            if not size:
                raise HTTPException(422, 'The uploaded file is empty.')
            validate(path, row['suffix'])
            return materials.finish_upload(row, size)
        except ExtractionError as error:
            path.unlink(missing_ok=True)
            raise HTTPException(422, str(error)) from None
        except sqlite3.IntegrityError:
            path.unlink(missing_ok=True)
            raise HTTPException(409, 'Another material version was uploaded concurrently. Retry this upload.') from None
        except BaseException:
            path.unlink(missing_ok=True)
            raise

    @router.post('/{id}/publish')
    def publish(offering_id: str, id: str, request: Request):
        manager(request, offering_id)
        return materials.publish(offering_id, id)

    @router.post('/{id}/retry', status_code=202)
    def retry(offering_id: str, id: str, request: Request):
        manager(request, offering_id)
        return materials.retry(offering_id, id)

    @router.get('/{id}/passages')
    def passages(offering_id: str, id: str, request: Request):
        visible(request, offering_id, id)
        return materials.passages(offering_id, id)

    @router.get('/{id}/passages/{passage_id}')
    def passage(offering_id: str, id: str, passage_id: str, request: Request):
        visible(request, offering_id, id)
        return materials.passage(offering_id, id, passage_id)

    @router.get('/{id}/file')
    def source_file(offering_id: str, id: str, request: Request):
        row = visible(request, offering_id, id)
        if row['kind'] != 'document':
            raise HTTPException(404, 'Recordings are available through approved lecture clips.')
        if not Path(row['storage_path']).is_file():
            raise HTTPException(503, 'The original source file is unavailable. Restore it or upload a new version.')
        return FileResponse(row['storage_path'], filename=row['filename'], content_disposition_type='attachment',
                            headers={'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'private, no-store'})

    return router
