"""Bounded in-process admission and content-free correlated request logs."""
import hashlib
import logging
import os
import threading
import time
import uuid
from collections import defaultdict, deque
from contextlib import contextmanager

from fastapi import HTTPException
from starlette.responses import JSONResponse
from athena_agent.llm import DependencyError


class ModelCapacity(Exception):
    pass


class ModelAdmission:
    def __init__(self):
        self.lock = threading.Lock()
        self.active = 0
        self.calls = deque()

    @contextmanager
    def slot(self):
        now = time.monotonic()
        with self.lock:
            while self.calls and self.calls[0] <= now - 60:
                self.calls.popleft()
            if self.active >= int(os.environ.get('ATHENA_MODEL_CONCURRENCY', '4')) or len(self.calls) >= int(os.environ.get('ATHENA_MODEL_CALLS_PER_MINUTE', '60')):
                raise ModelCapacity('Model capacity unavailable; retry shortly')
            self.active += 1
            self.calls.append(now)
        try:
            yield
        finally:
            with self.lock:
                self.active -= 1


MODELS = ModelAdmission()


class BoundedLLM:
    def __init__(self, llm):
        self.llm = llm

    async def generate(self, messages, response_model):
        try:
            with MODELS.slot():
                return await self.llm.generate(messages, response_model)
        except ModelCapacity:
            raise DependencyError('Model capacity is temporarily unavailable.') from None


class OperationalLimits:
    def __init__(self, app):
        self.app = app
        self.requests = defaultdict(deque)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request_id = uuid.uuid4().hex
        peer = scope.get('client', ('unknown',))[0]
        now = time.monotonic()
        key = hashlib.sha256(peer.encode()).digest()
        queue = self.requests[key]
        while queue and queue[0] <= now - 60:
            queue.popleft()
        # Bound the admission map, including callers that rotate cookies.
        if len(self.requests) > 4096:
            self.requests = defaultdict(deque, {k: v for k, v in self.requests.items() if v and v[-1] > now - 60})
        if len(queue) >= int(os.environ.get('ATHENA_REQUESTS_PER_MINUTE', '300')):
            return await JSONResponse({'detail': 'Request quota reached. Retry shortly.'}, status_code=429, headers={'Retry-After': '60', 'X-Request-ID': request_id})(scope, receive, send)
        queue.append(now)
        scope.setdefault('state', {})['request_id'] = request_id
        status = 500
        async def tagged(message):
            nonlocal status
            if message['type'] == 'http.response.start':
                status = message['status']
                message.setdefault('headers', []).append((b'x-request-id', request_id.encode()))
            await send(message)
        body_bytes = 0
        upload = scope['path'].endswith('/materials') and scope['method'] == 'POST'
        async def bounded_receive():
            nonlocal body_bytes
            message = await receive()
            if message['type'] == 'http.request':
                body_bytes += len(message.get('body', b''))
                if not upload and body_bytes > 2 * 1024 * 1024:
                    raise HTTPException(413, 'Request body exceeds 2 MiB')
            return message
        try:
            await self.app(scope, bounded_receive, tagged)
        finally:
            # Route templates exclude private IDs, source names, query text and bodies.
            route = getattr(scope.get('route'), 'path', 'unmatched')
            logging.getLogger('athena.requests').info('request=%s method=%s route=%s status=%d duration_ms=%d', request_id, scope['method'], route, status, (time.monotonic() - now) * 1000)
