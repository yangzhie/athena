"""Run as a separate private process with Docker access; the API needs no socket."""
import argparse
import os
import selectors
import signal
import subprocess
import time
from pathlib import Path

from ..env import load_dotenv
from .store import Executions

DEFAULT_IMAGE = 'python:3.12-slim'
TIMEOUT = 5
OUTPUT_LIMIT = 65536


def cleanup(name):
    if not name or not name.startswith('athena-exec-'):
        return
    try:
        removed = subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        if removed.returncode == 0:
            return True
        # A removed/nonexistent container is already clean; daemon failure is not.
        available = subprocess.run(['docker', 'info', '--format', '{{.ServerVersion}}'], capture_output=True, timeout=5)
        if available.returncode == 0:
            return True
    except (OSError, subprocess.TimeoutExpired):
        pass  # The persistent sweep retries cleanup when Docker is reachable.
    return False


def execute(source, name, cancelled=lambda: False, image=None):
    """No shell, mounts, application env or secrets. Source enters on stdin only."""
    if len(source.encode()) > 16384:
        return None, 'Python source exceeds 16 KiB'
    args = ['docker', 'run', '--rm', '--name', name, '--label', 'athena.execution=true',
            '--network', 'none', '--read-only', '--memory', '256m', '--memory-swap', '256m',
            '--pids-limit', '32', '--cpus', '1', '--user', '65534:65534',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--ulimit', 'nofile=64:64',
            '--tmpfs', '/tmp:rw,noexec,nosuid,size=16m,mode=1777', '--workdir', '/tmp',
            '--log-driver', 'none', '--interactive', '--pull', 'never',
            image or os.environ.get('ATHENA_PYTHON_IMAGE', DEFAULT_IMAGE), 'python', '-I', '-B', '-']
    process = None
    output = {'stdout': bytearray(), 'stderr': bytearray()}
    reason = None
    started = time.monotonic()
    try:
        process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        pending = memoryview(source.encode())
        with selectors.DefaultSelector() as selector:
            for stream, key in [(process.stdin, 'stdin'), (process.stdout, 'stdout'), (process.stderr, 'stderr')]:
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_WRITE if key == 'stdin' else selectors.EVENT_READ, key)
            while selector.get_map():
                if cancelled():
                    reason = 'Cancelled'
                    break
                if time.monotonic() - started >= TIMEOUT:
                    reason = 'TimeoutExceeded'
                    break
                for key, _ in selector.select(.05):
                    stream, target = key.fileobj, key.data
                    if target == 'stdin':
                        try:
                            sent = os.write(stream.fileno(), pending[:8192]) if pending else 0
                            pending = pending[sent:]
                        except BrokenPipeError:
                            pending = memoryview(b'')
                        if not pending:
                            selector.unregister(stream)
                            stream.close()
                    else:
                        chunk = os.read(stream.fileno(), 8192)
                        if not chunk:
                            selector.unregister(stream)
                            continue
                        remaining = OUTPUT_LIMIT - sum(len(v) for v in output.values())
                        output[target].extend(chunk[:remaining])
                        if len(chunk) > remaining:
                            reason = 'OutputLimitExceeded'
                            break
                if reason:
                    break
        if reason:
            cleanup(name)
            process.kill()
        try:
            code = process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            cleanup(name)
            process.kill()
            code = process.wait(timeout=1)
        if code in (125, 126, 127) and not reason:
            return None, 'Python execution container is unavailable. Check the worker and configured image.'
        stdout = output['stdout'].decode('utf-8', errors='replace')
        stderr = output['stderr'].decode('utf-8', errors='replace')
        result = {'ok': code == 0 and not reason, 'provenance': 'real-run', 'stdout': stdout,
                  'values': {}, 'trace': [], 'duration_ms': round((time.monotonic() - started) * 1000),
                  'capabilities': {'trace': False, 'variable_inspection': False}}
        if not result['ok']:
            result['error'] = {'type': reason or 'PythonError', 'message': reason or stderr or f'Python exited with status {code}'}
        elif stderr:
            result['stderr'] = stderr
        return result, None
    except OSError:
        return None, 'Python execution worker cannot reach Docker'
    finally:
        if process:
            if process.poll() is None:
                process.kill()
                process.wait()
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream and not stream.closed:
                    stream.close()
        cleanup(name)


def run_once(store):
    with store.lock:
        cleanup_queue = [r[0] for r in store.db.execute('SELECT container FROM execution_cleanup')]
    for name in cleanup_queue:
        if cleanup(name):
            with store.lock, store.db:
                store.db.execute('DELETE FROM execution_cleanup WHERE container=?', (name,))
    job, stale = store.claim()
    with store.lock:
        terminal = store.db.execute("SELECT container FROM executions WHERE container IS NOT NULL AND state NOT IN ('queued','running')").fetchall()
    for name in set(stale + [row[0] for row in terminal]):
        if cleanup(name):
            with store.lock, store.db:
                store.db.execute('UPDATE executions SET container=NULL WHERE container=?', (name,))
    if not job:
        return False
    try:
        result, error = execute(job['source'], job['container'], lambda: store.cancelled(job['id'], job['token']))
        store.finish(job, result, error)
    except BaseException:
        cleanup(job['container'])
        store.finish(job, error='Worker interrupted; submit a new run')
        raise
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    load_dotenv()
    store = Executions(Path(os.environ.get('ATHENA_DB', 'data/athena.db')))
    # SIGTERM unwinds execute's finally, including container removal.
    def stop(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    try:
        while True:
            worked = run_once(store)
            if args.once:
                break
            if not worked:
                time.sleep(.25)
    except KeyboardInterrupt:
        pass
    finally:
        store.db.close()


if __name__ == '__main__':
    main()
