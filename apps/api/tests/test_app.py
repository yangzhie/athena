from fastapi.testclient import TestClient

from athena_api.app import create_app


def test_health():
    assert TestClient(create_app()).get("/health").json() == {"status": "ok"}
