import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from datetime import datetime, timezone

from athena_agent.contracts import RequestContext
from fastapi import HTTPException

from ..sessions.models import LearningSession


class Lifecycle:
    def __init__(self, spaces, sessions, learning):
        self.spaces, self.sessions, self.learning = spaces, sessions, learning
        self.db = sqlite3.connect(spaces.path, check_same_thread=False, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.db.execute('PRAGMA foreign_keys=ON')
        # Clear freed payload pages too. Operators must expire backups under the same policy.
        self.db.execute('PRAGMA secure_delete=ON')
        with self.db:
            self.db.executescript('''
                CREATE TABLE IF NOT EXISTS private_cleanup (
                    session TEXT PRIMARY KEY, student TEXT NOT NULL, offering TEXT NOT NULL,
                    state TEXT NOT NULL, created REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS execution_cleanup (container TEXT PRIMARY KEY);
            ''')

    def unavailable(self, session):
        with self.lock:
            return bool(self.db.execute('SELECT 1 FROM private_cleanup WHERE session=?', (session,)).fetchone())

    def delete(self, student, offering, session):
        with self.lock, self.db:
            old = self.db.execute('SELECT * FROM private_cleanup WHERE session=? AND student=? AND offering=?', (session, student, offering)).fetchone()
            stored = self.sessions.store.get(student, session)
            operation = self.db.execute('SELECT 1 FROM session_operations WHERE student_id=? AND offering_id=? AND session_id=?', (student, offering, session)).fetchone()
            if not old and not operation and (not stored or stored.offering_id != offering):
                return  # Idempotent deletion, also indistinguishable from an unowned ID.
            self.db.execute('INSERT OR IGNORE INTO private_cleanup VALUES (?,?,?,?,?)', (session, student, offering, 'pending', time.time()))
            # Revoke shares immediately even if agent cleanup subsequently fails.
            if stored:
                data = stored.model_copy(update={'shared': False, 'share_token': None, 'shared_at': None})
                self.db.execute('UPDATE learning_sessions SET data=? WHERE id=? AND student_id=?', (data.model_dump_json(), session, student))
            self.db.execute("UPDATE executions SET state='cancelled' WHERE session=? AND state IN ('queued','running')", (session,))
        self.finish(session)

    def finish(self, session):
        with self.lock:
            row = self.db.execute('SELECT * FROM private_cleanup WHERE session=?', (session,)).fetchone()
        if not row:
            return
        student, offering = row['student'], row['offering']
        store = getattr(self.sessions.tutor, 'store', None)
        owned_store = False
        # Retention must still erase old AI state when credentials are unavailable.
        path = Path(os.environ.get('ATHENA_AGENT_DB', str(self.spaces.path.parent / 'agent.db')))
        if store is None and path.exists():
            from athena_agent.sqlite_memory import SQLiteLearningMemory
            store = SQLiteLearningMemory(path)
            owned_store = True
        if store is not None:
            if not hasattr(store, 'delete'):
                raise HTTPException(503, 'Tutor cleanup is unavailable; deletion is queued and sharing is revoked')
            try:
                store.delete(RequestContext(request_id='private-cleanup', learner_id=student, session_id=session))
            except Exception:
                raise HTTPException(503, 'Tutor cleanup is temporarily unavailable; deletion will resume') from None
            finally:
                if owned_store:
                    store.close()
        with self.lock, self.db:
            self.db.execute('BEGIN IMMEDIATE')
            self.db.execute('INSERT OR IGNORE INTO execution_cleanup SELECT container FROM executions WHERE session=? AND container IS NOT NULL', (session,))
            for table in ('playground_operations', 'playground_events', 'playground_applied_runs', 'playground_turns', 'playground_replacements', 'playgrounds', 'executions'):
                self.db.execute(f'DELETE FROM {table} WHERE session=?', (session,))
            self._practice(student, offering, session)
            self.db.execute('DELETE FROM learner_evidence_state WHERE id IN (SELECT id FROM learner_evidence WHERE session_id=?)', (session,))
            self.db.execute('DELETE FROM learner_evidence WHERE session_id=?', (session,))
            self.db.execute('DELETE FROM session_concepts WHERE session_id=?', (session,))
            # No individual-linked event survives deletion. Future analytics can add
            # separately suppressed cohort rollups without keeping private IDs.
            self.db.execute("DELETE FROM aggregate_events WHERE session_id=? OR (outcome LIKE 'practice_%' AND environment_id IN (SELECT id FROM environments WHERE student_id=? AND offering_id=?))", (session, student, offering))
            self.db.execute('DELETE FROM session_operations WHERE session_id=?', (session,))
            self.db.execute('DELETE FROM session_messages WHERE session_id=?', (session,))
            self.db.execute('DELETE FROM session_answers WHERE session_id=?', (session,))
            self.db.execute('DELETE FROM learning_sessions WHERE id=? AND student_id=?', (session, student))
            self._profile(student)
            self.db.execute('DELETE FROM private_cleanup WHERE session=?', (session,))
        # No Docker access is needed by the API. A persistent queue carries only
        # generated container names; the private worker removes artifacts.
        if hasattr(self.sessions.tutor, '_states'):
            self.sessions.tutor._states.pop((student, session), None)

    def _practice(self, student, offering, session):
        items = self.db.execute('SELECT id,data FROM private_practice WHERE student_id=? AND offering_id=?', (student, offering)).fetchall()
        for item in items:
            removed = {r[0] for r in self.db.execute('SELECT variant FROM private_practice_provenance WHERE student_id=? AND offering_id=? AND item=? AND session=?', (student, offering, item['id'], session))}
            provenance = self.db.execute('SELECT 1 FROM private_practice_provenance WHERE student_id=? AND offering_id=? AND item=?', (student, offering, item['id'])).fetchone()
            if not removed and provenance:
                continue
            # Legacy variants without provenance are conservatively purged.
            data = json.loads(item['data'])
            self.db.execute('DELETE FROM private_practice_provenance WHERE student_id=? AND offering_id=? AND item=? AND session=?', (student, offering, item['id'], session))
            retained = {r[0] for r in self.db.execute('SELECT variant FROM private_practice_provenance WHERE student_id=? AND offering_id=? AND item=?', (student, offering, item['id']))}
            data['variants'] = [v for v in data['variants'] if v['id'] in retained]
            if data['variants']:
                self.db.execute('UPDATE private_practice SET data=? WHERE student_id=? AND offering_id=? AND id=?', (json.dumps(data), student, offering, item['id']))
            else:
                self.db.execute('DELETE FROM private_practice WHERE student_id=? AND offering_id=? AND id=?', (student, offering, item['id']))
            for table in ('cards', 'attempts', 'review_logs'):
                self.db.execute(f'DELETE FROM {table} WHERE student_id=? AND offering_id=? AND item_id=?', (student, offering, item['id']))
        # Receipts can embed removed question text/rubrics; they contain no session key.
        self.db.execute('DELETE FROM srs_commands WHERE student_id=? AND offering_id=?', (student, offering))

    def _profile(self, student):
        self.db.execute('DELETE FROM learner_concepts WHERE student_id=?', (student,))
        self.db.execute('DELETE FROM learner_concept_offerings WHERE student_id=?', (student,))
        remaining = self.db.execute('SELECT e.*,s.status,s.note FROM learner_evidence e LEFT JOIN learner_evidence_state s ON s.id=e.id WHERE e.student_id=? ORDER BY e.created_at,e.id', (student,)).fetchall()
        for row in remaining:
            status, note = row['status'] or 'unknown', row['note'] or 'More evidence is needed.'
            previous = self.db.execute('SELECT status,note FROM learner_concepts WHERE student_id=? AND concept_id=?', (student, row['concept_id'])).fetchone()
            if previous and (status == 'unknown' or row['outcome'] == 'correct' and previous['status'] == 'mastered'):
                status, note = previous['status'], previous['note']
            self.db.execute('INSERT INTO learner_concepts VALUES (?,?,?,?,1,?) ON CONFLICT(student_id,concept_id) DO UPDATE SET status=excluded.status,note=excluded.note,evidence_count=evidence_count+1,updated_at=excluded.updated_at',
                (student, row['concept_id'], status, note, row['created_at']))
            self.db.execute('INSERT OR IGNORE INTO learner_concept_offerings VALUES (?,?,?)', (student, row['offering_id'], row['concept_id']))
        self.db.execute('DELETE FROM concepts WHERE public=0 AND id NOT IN (SELECT concept_id FROM session_concepts) AND id NOT IN (SELECT concept_id FROM learner_evidence)')

    def sweep(self, now=None):
        now = time.time() if now is None else now
        days = float(os.environ.get('ATHENA_PRIVATE_RETENTION_DAYS', '30'))
        if days <= 0:
            raise ValueError('ATHENA_PRIVATE_RETENTION_DAYS must be positive')
        cutoff = now - days * 86400
        with self.lock:
            pending = [r[0] for r in self.db.execute('SELECT session FROM private_cleanup')]
            expired = [LearningSession.model_validate_json(r[0]) for r in self.db.execute('SELECT data FROM learning_sessions')]
            pending_starts = [json.loads(r[0])['session'] for r in self.db.execute('SELECT data FROM session_operations WHERE complete=0')]
            known = {s.id for s in expired}
            expired.extend(LearningSession.model_validate(s) if not isinstance(s.get('created_at'), str) else LearningSession.model_validate_json(json.dumps(s)) for s in pending_starts if s['id'] not in known)
        count = 0
        for session in pending:
            self.finish(session)
            count += 1
        for session in expired:
            if session.id not in pending and session.created_at.timestamp() <= cutoff:
                self.delete(session.student_id, session.offering_id, session.id)
                count += 1
        with self.lock, self.db:
            # Practice-only data and old pending creation operations also expire.
            iso = datetime.fromtimestamp(cutoff, timezone.utc).isoformat()
            self.db.execute('DELETE FROM srs_commands WHERE created_at<?', (cutoff,))
            self.db.execute('DELETE FROM attempts WHERE created_at<?', (iso,))
            self.db.execute('DELETE FROM review_logs WHERE reviewed_at<?', (iso,))
            self.db.execute('DELETE FROM cards WHERE created_at<?', (iso,))
            self.db.execute('DELETE FROM aggregate_events WHERE created_at<?', (cutoff,))
        return count
