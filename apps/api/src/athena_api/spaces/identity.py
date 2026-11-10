"""Pure ASGI middleware: private server-owned identity and same-origin writes."""
import os
import sqlite3
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from starlette.responses import JSONResponse

COOKIE = 'athena_session'


class AnonymousIdentity:
    def __init__(self, app, spaces):
        self.app, self.spaces = app, spaces

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        if scope['path'] in {'/health', '/ready', '/tutor/status'} and scope['method'] in {'GET', 'HEAD'}:
            return await self.app(scope, receive, send)
        request = Request(scope)
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            origin = request.headers.get('origin')
            if request.headers.get('sec-fetch-site') == 'cross-site' or (origin and urlsplit(origin).netloc != request.headers.get('host')):
                return await JSONResponse({'detail': 'Cross-origin writes are not allowed.'}, status_code=403)(scope, receive, send)
        try:
            student, token = self.spaces.identity(request.cookies.get(COOKIE))
            scope.setdefault('state', {})['student_id'] = student
            parts = scope['path'].split('/')
            if len(parts) >= 3 and parts[1] == 'units':
                self.spaces.get(student, parts[2])
        except HTTPException as error:
            return await JSONResponse({'detail': error.detail}, status_code=error.status_code)(scope, receive, send)
        except sqlite3.Error:
            return await JSONResponse({'detail': 'Study space storage is unavailable.'}, status_code=503)(scope, receive, send)

        async def with_cookie(message):
            if token and message['type'] == 'http.response.start':
                response = JSONResponse(None)
                response.set_cookie(COOKIE, token, httponly=True, samesite='lax', max_age=30 * 86400,
                                    secure=scope.get('scheme') == 'https' or os.environ.get('ATHENA_SECURE_COOKIES') == '1')
                message.setdefault('headers', []).append((b'set-cookie', response.headers['set-cookie'].encode('latin-1')))
            await send(message)
        await self.app(scope, receive, with_cookie)
