import json
import sqlite3
import time
import uuid
from pathlib import Path
from threading import RLock

from fastapi import HTTPException


class Executions:
    MAX_QUEUED = 16
    MAX_CONCURRENT = 2

    def __init__(self, path: Path):
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.lock = RLock()
        with self.db:
            self.db.executescript('''
                CREATE TABLE IF NOT EXISTS executions (
                    id TEXT PRIMARY KEY, student TEXT NOT NULL, offering TEXT NOT NULL,
                    session TEXT NOT NULL, generation TEXT NOT NULL, object_id TEXT NOT NULL, run_id INTEGER NOT NULL,
                    actor TEXT NOT NULL, source TEXT NOT NULL, state TEXT NOT NULL,
                    created REAL NOT NULL, updated REAL NOT NULL, token TEXT,
                    container TEXT, result TEXT, error TEXT,
                    UNIQUE(session, generation, object_id, run_id)
                );
                CREATE INDEX IF NOT EXISTS execution_queue ON executions(state, created);
            ''')

    def enqueue(self, db, student, offering, session, generation, run, actor):
        # Caller owns the transaction: the checkpoint and the job commit together.
        existing = db.execute('SELECT id FROM executions WHERE session=? AND generation=? AND object_id=? AND run_id=?',
                              (session, generation, run['object_id'], run['run_id'])).fetchone()
        if existing:
            return existing[0]
        if len(run['source'].encode()) > 16384:
            raise HTTPException(413, 'Python source exceeds 16 KiB')
        if db.execute("SELECT count(*) FROM executions WHERE state='queued'").fetchone()[0] >= self.MAX_QUEUED:
            raise HTTPException(429, 'Execution queue is full. Retry shortly.')
        if db.execute("SELECT count(*) FROM executions WHERE student=? AND state IN ('queued','running')", (student,)).fetchone()[0] >= 2:
            raise HTTPException(429, 'This Environment already has two pending executions.')
        job = uuid.uuid4().hex
        now = time.time()
        db.execute('INSERT INTO executions(id,student,offering,session,generation,object_id,run_id,actor,source,state,created,updated) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                   (job, student, offering, session, generation, run['object_id'], run['run_id'], actor, run['source'], 'queued', now, now))
        return job

    def list(self, student, session):
        with self.lock:
            rows = self.db.execute('SELECT * FROM executions WHERE student=? AND session=? ORDER BY created', (student, session)).fetchall()
        return [self.public(r) for r in rows]

    @staticmethod
    def public(row):
        return {k: row[k] for k in ('id', 'object_id', 'run_id', 'actor', 'state', 'created', 'error')} | {
            'result': json.loads(row['result']) if row['result'] else None,
            'capabilities': {'trace': False, 'variable_inspection': False},
        }

    def cancel(self, student, session, job):
        with self.lock, self.db:
            row = self.db.execute('SELECT * FROM executions WHERE id=? AND student=? AND session=?', (job, student, session)).fetchone()
            if not row:
                raise HTTPException(404, 'Execution not found')
            self.db.execute("UPDATE executions SET state='cancelled',updated=? WHERE id=? AND state IN ('queued','running')", (time.time(), job))

    def cancelled(self, job, token):
        with self.lock:
            row = self.db.execute('SELECT state,token FROM executions WHERE id=?', (job,)).fetchone()
            return not row or row['state'] != 'running' or row['token'] != token

    def claim(self):
        with self.lock, self.db:
            self.db.execute('BEGIN IMMEDIATE')
            # The worker executes synchronously with an absolute 5-second limit.
            # A crashed worker's old job is never silently rerun as new evidence.
            stale = self.db.execute("SELECT container FROM executions WHERE state='running' AND updated<?", (time.time() - 30,)).fetchall()
            self.db.execute("UPDATE executions SET state='unavailable',error='Worker interrupted; submit a new run',updated=? WHERE state='running' AND updated<?", (time.time(), time.time() - 30))
            if self.db.execute("SELECT count(*) FROM executions WHERE state='running'").fetchone()[0] >= self.MAX_CONCURRENT:
                return None, [r[0] for r in stale if r[0]]
            row = self.db.execute("SELECT * FROM executions WHERE state='queued' ORDER BY created LIMIT 1").fetchone()
            if not row:
                return None, [r[0] for r in stale if r[0]]
            token = uuid.uuid4().hex
            name = f"athena-exec-{row['id']}-{token[:12]}"
            self.db.execute("UPDATE executions SET state='running',token=?,container=?,updated=? WHERE id=?", (token, name, time.time(), row['id']))
            return dict(row) | {'token': token, 'container': name}, [r[0] for r in stale if r[0]]

    def finish(self, job, result=None, error=None):
        with self.lock, self.db:
            self.db.execute("UPDATE executions SET state=?,result=?,error=?,updated=? WHERE id=? AND token=? AND state='running'",
                            ('finished' if result else 'unavailable', json.dumps(result) if result else None,
                             error, time.time(), job['id'], job['token']))
