#!/usr/bin/env python3
"""Start the single-host API, web, durable indexer and private execution worker."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
env = dict(os.environ)
data = Path(env.get('ATHENA_DATA_ROOT', ROOT / 'data')).resolve()
data.mkdir(parents=True, exist_ok=True)
env.setdefault('ATHENA_DB', str(data / 'athena.db'))
env.setdefault('ATHENA_AGENT_DB', str(data / 'agent.db'))
env.setdefault('ATHENA_MATERIAL_ROOT', str(data / 'materials'))
python = str(ROOT / 'apps/api/.venv/bin/python')

# The API runs the Playground engine from a built bundle; rebuild it when the package is newer
# (e.g. after pulling new scenes or components), or the server rejects them.
bundle = ROOT / 'packages/playground/dist/headless.mjs'
sources = (ROOT / 'packages/playground/src').rglob('*.ts*')
if not bundle.exists() or max(p.stat().st_mtime for p in sources) > bundle.stat().st_mtime:
    print('Building the Playground engine bundle…', flush=True)
    subprocess.run(['npm', 'run', 'build:headless', '-w', '@athena/playground'], cwd=ROOT, check=True)
commands = [
    [python, '-m', 'uvicorn', 'athena_api.app:create_app', '--factory', '--host', '127.0.0.1', '--port', '8000', '--no-access-log'],
    [python, '-m', 'athena_api.materials.worker'],
    [python, '-m', 'athena_api.execution.worker'],
    ['npm', 'run', 'dev', '-w', '@athena/web', '--', '--host', '127.0.0.1'],
]
processes = []
def stop(*_):
    raise KeyboardInterrupt
signal.signal(signal.SIGTERM, stop)
try:
    for command in commands:
        processes.append(subprocess.Popen(command, cwd=ROOT, env=env, start_new_session=True))
    while all(p.poll() is None for p in processes):
        time.sleep(.25)
except KeyboardInterrupt:
    pass
finally:
    for process in processes:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
    for process in processes:
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
    if any(p.returncode not in (0, -signal.SIGTERM, -signal.SIGINT) for p in processes):
        sys.exit(1)
