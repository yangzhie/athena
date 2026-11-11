"""The test transport must keep real worker results and exceptions observable."""

import asyncio
import threading

import pytest
from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

from .http_client import TestClient


def test_requests_complete_without_socket_wakeups(monkeypatch):
    # Reproduce the restricted runner even on machines with working wakeups.
    monkeypatch.setattr(asyncio.SelectorEventLoop, "_write_to_self", lambda _self: None)
    app = FastAPI()

    @app.get("/worker")
    async def worker():
        return {"worker": await run_in_threadpool(threading.get_ident), "loop": threading.get_ident()}

    def fail():
        raise RuntimeError("worker failure")

    @app.get("/failure")
    async def failure():
        await run_in_threadpool(fail)

    with TestClient(app) as client:
        response = client.get("/worker")
        assert response.status_code == 200
        assert response.json()["worker"] != response.json()["loop"]
        with pytest.raises(RuntimeError, match="worker failure"):
            client.get("/failure")
