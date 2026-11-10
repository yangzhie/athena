import asyncio
import json

import pytest
from athena_agent.llm import DependencyError, MockLLM
from athena_api.operations import BoundedLLM, ModelAdmission, ModelCapacity
from athena_api.playground.bridge import catalog

from .test_playground_persistence import setup, bundle


def test_model_admission_bounds_concurrency_and_call_rate(monkeypatch):
    admission = ModelAdmission()
    monkeypatch.setenv('ATHENA_MODEL_CONCURRENCY', '1')
    monkeypatch.setenv('ATHENA_MODEL_CALLS_PER_MINUTE', '1')
    with admission.slot():
        with pytest.raises(ModelCapacity):
            with admission.slot():
                pass
    assert admission.active == 0
    with pytest.raises(ModelCapacity):
        with admission.slot():
            pass


def test_readiness_and_correlated_logs_never_contain_private_content(tmp_path, caplog):
    client, service, student, offering, session, base = setup(tmp_path)
    with caplog.at_level('INFO', logger='athena.requests'):
        response = client.get(base)
    assert len(response.headers['X-Request-ID']) == 32
    assert session not in caplog.text and student not in caplog.text
    assert '/units/{offering_id}/sessions/{session_id}/playground' in caplog.text
    readiness = client.get('/ready').json()
    assert not readiness['ready'] and readiness['workers'] == {'execution': False, 'indexing': False}


def test_generated_playground_catalog_matches_runtime():
    from pathlib import Path
    stored = json.loads((Path(__file__).parents[3] / 'packages/shared/playground.json').read_text())
    schemas = stored['schemas']
    assert stored == catalog()
    assert set(schemas) >= {'Scene', 'Action', 'Check', 'CanvasSnapshot', 'ToolCall', 'ToolResult', 'RunResult', 'Observation'}


def test_health_checks_do_not_create_identities_and_requests_are_rate_limited(tmp_path, monkeypatch):
    from .test_playground_persistence import browser
    client, service = browser(tmp_path / 'host.db')
    monkeypatch.setenv('ATHENA_REQUESTS_PER_MINUTE', '2')
    assert client.get('/health').status_code == 200
    assert client.get('/ready').status_code == 503
    assert service.spaces.db.execute('SELECT count(*) FROM anonymous_identities').fetchone()[0] == 0
    limited = client.get('/health')
    assert limited.status_code == 429 and limited.headers['Retry-After'] == '60'
