import hashlib
import json
import sqlite3
from threading import RLock
import time
import uuid

from fastapi import HTTPException

from ..execution.store import Executions
from . import bridge


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


class Playgrounds:
    def __init__(self, spaces, sessions):
        self.spaces = spaces
        self.sessions = sessions
        self.executions = Executions(spaces.path)
        self.db = sqlite3.connect(spaces.path, check_same_thread=False, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.lock = RLock()
        with self.lock, self.db:
            self.db.executescript('''
                CREATE TABLE IF NOT EXISTS playgrounds (
                    session TEXT PRIMARY KEY, student TEXT NOT NULL, offering TEXT NOT NULL,
                    generation TEXT NOT NULL, revision INTEGER NOT NULL,
                    checkpoint TEXT NOT NULL, updated REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS playground_operations (
                    session TEXT NOT NULL, operation TEXT NOT NULL, fingerprint TEXT NOT NULL,
                    response TEXT NOT NULL, created REAL NOT NULL, PRIMARY KEY(session,operation)
                );
                CREATE TABLE IF NOT EXISTS playground_events (
                    id INTEGER PRIMARY KEY, session TEXT NOT NULL, generation TEXT NOT NULL,
                    revision INTEGER NOT NULL, event TEXT NOT NULL, created REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS playground_applied_runs (
                    execution TEXT PRIMARY KEY, session TEXT NOT NULL
                );
            ''')

    def authorize(self, student, offering, session):
        try:
            return self.sessions._get(student, session, offering)
        except Exception as error:
            from ..sessions.service import NotFound
            if isinstance(error, NotFound):
                raise HTTPException(404, 'Learning session not found') from None
            raise

    def _row(self, session):
        return self.db.execute('SELECT * FROM playgrounds WHERE session=?', (session,)).fetchone()

    def _view(self, row, data=None):
        if row is None:
            return {'revision': 0, 'catalog_version': bridge.catalog()['catalog_version'], 'checkpoint': None,
                    'snapshot': None, 'executions': []}
        if data is None:
            data = bridge.transition(json.loads(row['checkpoint']))
        return {k: data[k] for k in ('catalog_version', 'checkpoint', 'snapshot')} | {
            'revision': row['revision'], 'executions': self.executions.list(row['student'], row['session'])}

    def get(self, student, offering, session):
        self.authorize(student, offering, session)
        with self.lock:
            self._reconcile(session)
            return self._view(self._row(session))

    def command(self, student, offering, session, operation, revision, command, *, trusted=False):
        self.authorize(student, offering, session)
        if not trusted and command.get('kind') not in ('action', 'accept', 'reject'):
            raise HTTPException(422, 'Unsupported student command')
        if len(encoded(command).encode()) > 65536:
            raise HTTPException(413, 'Playground command too large')
        digest = hashlib.sha256(encoded({'revision': revision, 'command': command}).encode()).hexdigest()
        with self.lock:
            old = self.db.execute('SELECT * FROM playground_operations WHERE session=? AND operation=?', (session, operation)).fetchone()
            if old:
                if old['fingerprint'] != digest:
                    raise HTTPException(409, 'Operation ID already used for a different command')
                return json.loads(old['response'])
            self._reconcile(session)
            row = self._row(session)
            current = row['revision'] if row else 0
            if current != revision:
                raise HTTPException(409, 'Playground changed. Refresh its snapshot before applying this command.')
            if row is None and command.get('kind') != 'open' and command.get('call', {}).get('name') != 'open_playground':
                raise HTTPException(409, 'Open a scene first')
            checkpoint = json.loads(row['checkpoint']) if row else None
            data = bridge.transition(checkpoint, command)
            generation = uuid.uuid4().hex if command.get('kind') == 'open' or command.get('call', {}).get('name') == 'open_playground' else row['generation']
            now = time.time()
            with self.db:
                self.db.execute('BEGIN IMMEDIATE')
                replay = self.db.execute('SELECT * FROM playground_operations WHERE session=? AND operation=?', (session, operation)).fetchone()
                if replay:
                    if replay['fingerprint'] != digest:
                        raise HTTPException(409, 'Operation ID already used for a different command')
                    return json.loads(replay['response'])
                # Another API process may have committed while the TS adapter ran.
                actual = self._row(session)
                if (actual['revision'] if actual else 0) != current:
                    raise HTTPException(409, 'Playground changed. Refresh its snapshot.')
                self.authorize(student, offering, session)
                self.db.execute('INSERT INTO playgrounds VALUES (?,?,?,?,?,?,?) ON CONFLICT(session) DO UPDATE SET generation=excluded.generation,revision=excluded.revision,checkpoint=excluded.checkpoint,updated=excluded.updated',
                                (session, student, offering, generation, current + 1, encoded(data['checkpoint']), now))
                actor = 'agent' if trusted else 'student'
                for run in data['pending_runs']:
                    self.executions.enqueue(self.db, student, offering, session, generation, run, actor)
                self._events(session, generation, current + 1, data['events'])
                response = {k: data[k] for k in ('catalog_version', 'checkpoint', 'snapshot', 'result')} | {'revision': current + 1}
                self.db.execute('INSERT INTO playground_operations VALUES (?,?,?,?,?)', (session, operation, digest, encoded(response), now))
            return response

    def _events(self, session, generation, revision, events):
        for event in events:
            # The adapter accepts only committed actions; no pointer/animation frames.
            self.db.execute('INSERT INTO playground_events(session,generation,revision,event,created) VALUES (?,?,?,?,?)',
                            (session, generation, revision, encoded(event), time.time()))

    def _reconcile(self, session):
        row = self._row(session)
        if not row:
            return
        jobs = self.db.execute('''SELECT * FROM executions WHERE session=? AND generation=? AND state IN ('finished','cancelled','unavailable')
            AND id NOT IN (SELECT execution FROM playground_applied_runs) ORDER BY created''', (session, row['generation'])).fetchall()
        for job in jobs:
            checkpoint = json.loads(row['checkpoint'])
            obj = checkpoint['state']['objects'].get(job['object_id'])
            matches = obj and obj['state'].get('runId') == job['run_id'] and obj['state'].get('running')
            result = json.loads(job['result']) if job['result'] else {
                'ok': False, 'provenance': 'real-run', 'stdout': '', 'values': {}, 'trace': [],
                'error': {'type': 'ExecutionUnavailable', 'message': job['error'] or job['state']}}
            # Infrastructure failure is not verified output: clear running without inventing a result.
            if matches and not job['result']:
                obj['state']['running'] = False
                data = bridge.transition(checkpoint)
            elif matches:
                data = bridge.transition(checkpoint, {'kind': 'execution', 'object_id': job['object_id'], 'run_id': job['run_id'], 'result': result, 'actor': job['actor']})
            else:
                data = None
            with self.db:
                self.db.execute('BEGIN IMMEDIATE')
                actual = self._row(session)
                if not actual or actual['revision'] != row['revision']:
                    return  # A concurrent process will reconcile against the latest state.
                if data:
                    self.db.execute('UPDATE playgrounds SET revision=revision+1,checkpoint=?,updated=? WHERE session=?', (encoded(data['checkpoint']), time.time(), session))
                    self._events(session, row['generation'], row['revision'] + 1, data['events'])
                self.db.execute('INSERT OR IGNORE INTO playground_applied_runs VALUES (?,?)', (job['id'], session))
            row = self._row(session)
