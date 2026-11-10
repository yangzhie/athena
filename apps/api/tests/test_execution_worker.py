"""Offline scheduling tests, plus explicit opt-in real Docker isolation checks."""
import os
import subprocess
import time
import uuid

import pytest

from athena_api.execution.store import Executions
from athena_api.execution.worker import execute


def test_queue_cancellation_and_fencing(tmp_path):
    store = Executions(tmp_path / 'host.db')
    with store.db:
        first = store.enqueue(store.db, 'student', 'offering', 'session', 'generation', {'object_id': 'code', 'run_id': 1, 'source': 'print(1)'}, 'student')
        assert store.enqueue(store.db, 'student', 'offering', 'session', 'generation', {'object_id': 'code', 'run_id': 1, 'source': 'print(1)'}, 'student') == first
    job, _ = store.claim()
    assert job['id'] == first
    store.cancel('student', 'session', first)
    assert store.cancelled(first, job['token'])
    store.finish(job, {'ok': True})
    assert store.list('student', 'session')[0]['state'] == 'cancelled'
    with store.db:
        store.enqueue(store.db, 'student', 'offering', 'session', 'generation', {'object_id': 'code', 'run_id': 2, 'source': 'print(2)'}, 'student')
    stale, _ = store.claim()
    with store.db:
        store.db.execute('UPDATE executions SET updated=? WHERE id=?', (time.time() - 40, stale['id']))
    claimed, cleanup = store.claim()
    assert claimed is None and cleanup == [stale['container']]
    store.finish(stale, {'ok': True})
    assert store.list('student', 'session')[1]['state'] == 'unavailable'


@pytest.mark.skipif(os.environ.get('ATHENA_TEST_DOCKER') != '1', reason='Opt-in real isolated container checks')
@pytest.mark.parametrize('source,expected,error', [
    ('print(6*7)', '42', None),
    ('while True: pass', '', 'TimeoutExceeded'),
    ('while True: print("x"*8192)', '', 'OutputLimitExceeded'),
    ('import os\nprint(os.getuid())\nprint(os.path.exists("/app"))\nprint(os.environ.get("OPENAI_API_KEY"))\ntry:\n open("/escape", "w").write("bad")\nexcept OSError:\n print("readonly")\nimport socket\ns=socket.socket()\ns.settimeout(.5)\ntry:\n s.connect(("1.1.1.1", 443))\nexcept OSError:\n print("offline")', 'offline', None),
    ('raise ValueError("expected")', '', 'PythonError'),
])
def test_real_container_limits_and_cleanup(source, expected, error):
    name = 'athena-exec-test-' + uuid.uuid4().hex
    result, unavailable = execute(source, name)
    assert unavailable is None, unavailable
    assert result['provenance'] == 'real-run' and result['trace'] == [] and result['values'] == {}
    assert not result['capabilities']['trace']
    if expected:
        assert expected in result['stdout']
    if 'os.getuid' in source:
        assert '65534\nFalse\nNone\nreadonly\noffline' in result['stdout']
    if error:
        assert result['error']['type'] == error
    assert len(result['stdout'].encode()) <= 65536
    assert subprocess.run(['docker', 'inspect', name], capture_output=True).returncode != 0
