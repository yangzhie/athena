"""Real ASGI requests with bounded selector waits for restricted test runners.

Some sandboxes cannot deliver asyncio's socket-based cross-thread wakeups.
Starlette's TestClient and FastAPI's synchronous dependencies both need those
wakeups. Polling also drains the real event loop's queued callbacks without
replacing routes, dependencies, worker threads, or application behavior.
"""

import asyncio
import selectors

from fastapi.testclient import TestClient as StarletteTestClient


class _PollingSelector(selectors.DefaultSelector):
    def select(self, timeout=None):
        return super().select(0.01 if timeout is None else min(timeout, 0.01))


def _test_loop():
    return asyncio.SelectorEventLoop(selector=_PollingSelector())


class TestClient(StarletteTestClient):
    __test__ = False

    def __init__(self, *args, **kwargs):
        options = dict(kwargs.pop("backend_options", None) or {})
        options.setdefault("loop_factory", _test_loop)
        super().__init__(*args, backend_options=options, **kwargs)
