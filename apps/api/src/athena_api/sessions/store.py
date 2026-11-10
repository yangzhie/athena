"""Storage for sessions and messages. Every method takes the student id and filters by it."""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Protocol

from .models import AnswerReceipt, LearningSession, Message
from .operations import Operation, SCHEMA as OPERATION_SCHEMA, match
from .tutor import TutorError


class AnswerConflict(ValueError):
    """A different answer was already accepted for this question."""


def _replay(previous: AnswerReceipt, submitted: AnswerReceipt) -> list[Message]:
    if not previous.same_submission(submitted):
        raise AnswerConflict("This question already has an answer; request a fresh question.")
    return previous.model_copy(deep=True).messages


def _complete_answer(store, student_id, session_id, receipt, updated_at):
    """Keep the existing store contract on the coordinated exchange transaction."""
    session = store.get(student_id, session_id)
    if session is None:
        raise LookupError("no such session")
    previous = store.answer_receipt(student_id, session_id, receipt.question_id)
    if previous:
        return _replay(previous, receipt)
    try:
        operation = store.begin_operation(Operation(id="answer:" + receipt.question_id, kind="answer", session=session,
                                                    payload=receipt.model_dump(exclude={"messages"})))
        operation.messages = receipt.messages
        return store.complete_operation(operation, updated_at).messages
    except TutorError as error:
        raise AnswerConflict(str(error)) from None


class SessionStore(Protocol):
    def list(self, student_id: str, offering_id: str) -> list[LearningSession]: ...
    def get(self, student_id: str, session_id: str) -> LearningSession | None: ...
    def put(self, session: LearningSession) -> None: ...
    def delete(self, student_id: str, session_id: str) -> bool: ...
    def messages(self, student_id: str, session_id: str) -> list[Message]: ...
    def add_message(self, student_id: str, message: Message) -> None: ...
    def answer_receipt(self, student_id: str, session_id: str, question_id: str) -> AnswerReceipt | None: ...
    def complete_answer(self, student_id: str, session_id: str, receipt: AnswerReceipt, updated_at: datetime) -> list[Message]:
        """Atomically store the exchange and receipt, or replay the existing result."""
        ...
    def operation(self, student_id: str, offering_id: str, operation_id: str) -> Operation | None: ...
    def begin_operation(self, operation: Operation) -> Operation: ...
    def complete_operation(self, operation: Operation, updated_at: datetime) -> Operation: ...
    def fail_operation(self, operation: Operation, error: str) -> None: ...
    def shared(self, offering_id: str) -> list[LearningSession]:
        """Sessions currently shared in an offering (for its lecturers)."""
        ...


class MemorySessionStore:
    def __init__(self) -> None:
        self.sessions: dict[str, LearningSession] = {}
        self.msgs: dict[str, list[Message]] = {}
        self.answers: dict[tuple[str, str], AnswerReceipt] = {}
        self._answer_lock = threading.RLock()
        self.operations: dict[tuple[str, str, str], Operation] = {}

    def list(self, student_id, offering_id):
        out = [s for s in self.sessions.values() if s.student_id == student_id and s.offering_id == offering_id]
        return sorted(out, key=lambda s: s.updated_at, reverse=True)

    def get(self, student_id, session_id):
        s = self.sessions.get(session_id)
        return s if s and s.student_id == student_id else None

    def put(self, session):
        self.sessions[session.id] = session

    def update_existing(self, session, fields=None):
        with self._answer_lock:
            if self.get(session.student_id, session.id) is None:
                raise LookupError('no such session')
            current = self.get(session.student_id, session.id)
            updated = current.model_copy(update={k: getattr(session, k) for k in fields}) if fields else session
            self.sessions[session.id] = updated
            return updated

    def reply_shared(self, token, message, now):
        with self._answer_lock:
            session = next((s for s in self.sessions.values() if s.id == message.session_id and s.shared and s.share_token == token), None)
            if session is None:
                raise LookupError('share revoked')
            self.msgs.setdefault(session.id, []).append(message)
            self.sessions[session.id] = session.model_copy(update={'updated_at': now, 'last_lecturer_reply_at': now})

    def delete(self, student_id, session_id):
        with self._answer_lock:
            if not self.get(student_id, session_id):
                return False
            self.operations = {k: v for k, v in self.operations.items() if v.session.id != session_id}
            del self.sessions[session_id]
            self.msgs.pop(session_id, None)
            self.answers = {key: value for key, value in self.answers.items() if key[0] != session_id}
            return True

    def messages(self, student_id, session_id):
        return list(self.msgs.get(session_id, [])) if self.get(student_id, session_id) else []

    def add_message(self, student_id, message):
        if self.get(student_id, message.session_id):
            self.msgs.setdefault(message.session_id, []).append(message)

    def shared(self, offering_id):
        return [s for s in self.sessions.values() if s.offering_id == offering_id and s.shared and s.share_token]

    def answer_receipt(self, student_id, session_id, question_id):
        with self._answer_lock:
            receipt = self.answers.get((session_id, question_id)) if self.get(student_id, session_id) else None
            return receipt.model_copy(deep=True) if receipt else None

    def complete_answer(self, student_id, session_id, receipt, updated_at):
        return _complete_answer(self, student_id, session_id, receipt, updated_at)

    def operation(self, student_id, offering_id, operation_id):
        with self._answer_lock:
            op = self.operations.get((student_id, offering_id, operation_id))
            return op.model_copy(deep=True) if op else None

    def begin_operation(self, operation):
        with self._answer_lock:
            key = (operation.session.student_id, operation.session.offering_id, operation.id)
            previous = self.operations.get(key)
            if previous and not previous.error:
                return match(previous, operation)
            if operation.kind != "start":
                session = self.get(operation.session.student_id, operation.session.id)
                if session is None or session.offering_id != operation.session.offering_id:
                    raise LookupError("no such session")
            if any(o.session.id == operation.session.id and not o.complete and not o.error for o in self.operations.values()):
                raise TutorError("A session operation is pending. Retry that operation first.", 409)
            self.operations[key] = operation.model_copy(deep=True)
            return operation.model_copy(deep=True)

    def fail_operation(self, operation, error):
        with self._answer_lock:
            key = (operation.session.student_id, operation.session.offering_id, operation.id)
            current = self.operations.get(key)
            if current and not current.complete:
                self.operations[key] = current.model_copy(update={"error": error})

    def complete_operation(self, operation, updated_at):
        with self._answer_lock:
            key = (operation.session.student_id, operation.session.offering_id, operation.id)
            previous = self.operations[key]
            if previous.complete:
                return match(previous, operation)
            session = self.sessions.get(operation.session.id) or operation.session
            if operation.kind != "start" and operation.session.id not in self.sessions:
                raise LookupError("no such session")
            session = session.model_copy(update={"updated_at": updated_at})
            self.sessions[session.id] = session
            self.msgs[session.id] = [*self.msgs.get(session.id, []), *operation.model_copy(deep=True).messages]
            if operation.kind == "answer":
                receipt = AnswerReceipt(**operation.payload, messages=operation.messages)
                self.answers[session.id, receipt.question_id] = receipt.model_copy(deep=True)
            operation = operation.model_copy(update={"session": session, "complete": True}, deep=True)
            self.operations[key] = operation
            return operation.model_copy(deep=True)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS learning_sessions (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    offering_id TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_by_student ON learning_sessions (student_id, offering_id, updated_at);
CREATE TABLE IF NOT EXISTS session_messages (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES learning_sessions(id) ON DELETE CASCADE,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_by_session ON session_messages (session_id, seq);
CREATE TABLE IF NOT EXISTS session_answers (
    session_id TEXT NOT NULL REFERENCES learning_sessions(id) ON DELETE CASCADE,
    question_id TEXT NOT NULL,
    data TEXT NOT NULL,
    PRIMARY KEY (session_id, question_id)
);
"""


class SqliteSessionStore:
    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.Lock()
        with self._lock, self._db:
            self._db.executescript(_SCHEMA + OPERATION_SCHEMA)

    def close(self) -> None:
        self._db.close()

    def list(self, student_id, offering_id):
        with self._lock:
            rows = self._db.execute(
                "SELECT data FROM learning_sessions WHERE student_id = ? AND offering_id = ? ORDER BY updated_at DESC",
                (student_id, offering_id),
            ).fetchall()
        return [LearningSession.model_validate_json(r[0]) for r in rows]

    def get(self, student_id, session_id):
        with self._lock:
            row = self._db.execute(
                "SELECT data FROM learning_sessions WHERE id = ? AND student_id = ?", (session_id, student_id)
            ).fetchone()
        return LearningSession.model_validate_json(row[0]) if row else None

    def put(self, s):
        with self._lock, self._db:
            self._db.execute(
                """INSERT INTO learning_sessions (id, student_id, offering_id, updated_at, data) VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET updated_at = excluded.updated_at, data = excluded.data
                   WHERE learning_sessions.student_id = excluded.student_id""",
                (s.id, s.student_id, s.offering_id, s.updated_at.isoformat(), s.model_dump_json()),
            )

    def update_existing(self, session, fields=None):
        with self._lock, self._db:
            self._db.execute('BEGIN IMMEDIATE')
            if self._db.execute("SELECT 1 FROM sqlite_master WHERE name='private_cleanup'").fetchone() and self._db.execute('SELECT 1 FROM private_cleanup WHERE session=?', (session.id,)).fetchone():
                raise LookupError('session deletion is pending')
            row = self._db.execute('SELECT data FROM learning_sessions WHERE id=? AND student_id=?', (session.id, session.student_id)).fetchone()
            if not row:
                raise LookupError('no such session')
            current = LearningSession.model_validate_json(row[0])
            updated = current.model_copy(update={k: getattr(session, k) for k in fields}) if fields else session
            self._db.execute('UPDATE learning_sessions SET data=?,updated_at=? WHERE id=? AND student_id=?',
                             (updated.model_dump_json(), updated.updated_at.isoformat(), session.id, session.student_id))
            return updated

    def reply_shared(self, token, message, now):
        with self._lock, self._db:
            self._db.execute('BEGIN IMMEDIATE')
            row = self._db.execute('SELECT data FROM learning_sessions WHERE id=?', (message.session_id,)).fetchone()
            session = LearningSession.model_validate_json(row[0]) if row else None
            if not session or not session.shared or session.share_token != token:
                raise LookupError('share revoked')
            self._db.execute('INSERT INTO session_messages(session_id,data) VALUES (?,?)', (session.id, message.model_dump_json()))
            session = session.model_copy(update={'updated_at': now, 'last_lecturer_reply_at': now})
            self._db.execute('UPDATE learning_sessions SET data=?,updated_at=? WHERE id=?', (session.model_dump_json(), now.isoformat(), session.id))

    def delete(self, student_id, session_id):
        with self._lock, self._db:
            self._db.execute("DELETE FROM session_operations WHERE session_id = ? AND student_id = ?", (session_id, student_id))
            cur = self._db.execute("DELETE FROM learning_sessions WHERE id = ? AND student_id = ?", (session_id, student_id))
        return cur.rowcount > 0

    def messages(self, student_id, session_id):
        if not self.get(student_id, session_id):
            return []
        with self._lock:
            rows = self._db.execute("SELECT data FROM session_messages WHERE session_id = ? ORDER BY seq", (session_id,)).fetchall()
        return [Message.model_validate_json(r[0]) for r in rows]

    def shared(self, offering_id):
        with self._lock:
            rows = self._db.execute("SELECT data FROM learning_sessions WHERE offering_id = ?", (offering_id,)).fetchall()
        sessions = [LearningSession.model_validate_json(r[0]) for r in rows]
        return [s for s in sessions if s.shared and s.share_token]

    def add_message(self, student_id, message):
        if not self.get(student_id, message.session_id):
            return
        with self._lock, self._db:
            self._db.execute("INSERT INTO session_messages (session_id, data) VALUES (?, ?)", (message.session_id, message.model_dump_json()))

    def answer_receipt(self, student_id, session_id, question_id):
        with self._lock:
            row = self._db.execute(
                """SELECT a.data FROM session_answers a JOIN learning_sessions s ON s.id = a.session_id
                   WHERE s.student_id = ? AND s.id = ? AND a.question_id = ?""",
                (student_id, session_id, question_id),
            ).fetchone()
        return AnswerReceipt.model_validate_json(row[0]) if row else None

    def complete_answer(self, student_id, session_id, receipt, updated_at):
        return _complete_answer(self, student_id, session_id, receipt, updated_at)

    def operation(self, student_id, offering_id, operation_id):
        with self._lock:
            row = self._db.execute("SELECT data FROM session_operations WHERE student_id=? AND offering_id=? AND operation_id=?",
                                   (student_id, offering_id, operation_id)).fetchone()
        return Operation.model_validate_json(row[0]) if row else None

    def begin_operation(self, operation):
        s = operation.session
        with self._lock, self._db:
            # Serialize reservation across independent connections before reading.
            self._db.execute("BEGIN IMMEDIATE")
            row = self._db.execute("SELECT data FROM session_operations WHERE student_id=? AND offering_id=? AND operation_id=?",
                                   (s.student_id, s.offering_id, operation.id)).fetchone()
            if row:
                previous = Operation.model_validate_json(row[0])
                if not previous.error:
                    return match(previous, operation)
                self._db.execute("DELETE FROM session_operations WHERE student_id=? AND offering_id=? AND operation_id=?",
                                 (s.student_id, s.offering_id, operation.id))
            if operation.kind != "start":
                session = self._db.execute("SELECT offering_id FROM learning_sessions WHERE id=? AND student_id=?", (s.id, s.student_id)).fetchone()
                if not session or session[0] != s.offering_id:
                    raise LookupError("no such session")
            pending = self._db.execute("SELECT 1 FROM session_operations WHERE session_id=? AND complete=0", (s.id,)).fetchone()
            if pending:
                raise TutorError("A session operation is pending. Retry that operation first.", 409)
            self._db.execute("INSERT INTO session_operations VALUES (?, ?, ?, ?, 0, ?)",
                             (s.student_id, s.offering_id, operation.id, s.id, operation.model_dump_json()))
        return operation

    def fail_operation(self, operation, error):
        s = operation.session
        with self._lock, self._db:
            row = self._db.execute("SELECT data FROM session_operations WHERE student_id=? AND offering_id=? AND operation_id=? AND complete=0",
                                   (s.student_id, s.offering_id, operation.id)).fetchone()
            if row:
                failed = Operation.model_validate_json(row[0]).model_copy(update={"error": error})
                self._db.execute("UPDATE session_operations SET complete=1, data=? WHERE student_id=? AND offering_id=? AND operation_id=? AND complete=0",
                                 (failed.model_dump_json(), s.student_id, s.offering_id, operation.id))

    def complete_operation(self, operation, updated_at):
        s = operation.session
        with self._lock, self._db:
            self._db.execute("BEGIN IMMEDIATE")
            row = self._db.execute("SELECT data FROM session_operations WHERE student_id=? AND offering_id=? AND operation_id=?",
                                   (s.student_id, s.offering_id, operation.id)).fetchone()
            if not row:
                raise LookupError("no such operation")
            previous = match(Operation.model_validate_json(row[0]), operation)
            if previous.complete:
                return previous
            row = self._db.execute("SELECT data FROM learning_sessions WHERE id=? AND student_id=?", (s.id, s.student_id)).fetchone()
            if operation.kind != "start" and not row:
                raise LookupError("no such session")
            s = LearningSession.model_validate_json(row[0]) if row else s
            s = s.model_copy(update={"updated_at": updated_at})
            self._db.execute("INSERT INTO learning_sessions VALUES (?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at, data=excluded.data",
                             (s.id, s.student_id, s.offering_id, s.updated_at.isoformat(), s.model_dump_json()))
            self._db.executemany("INSERT INTO session_messages (session_id, data) VALUES (?, ?)",
                                 [(s.id, m.model_dump_json()) for m in operation.messages])
            if operation.kind == "answer":
                receipt = AnswerReceipt(**operation.payload, messages=operation.messages)
                self._db.execute("INSERT INTO session_answers VALUES (?, ?, ?)", (s.id, receipt.question_id, receipt.model_dump_json()))
            operation = operation.model_copy(update={"session": s, "complete": True})
            self._db.execute("UPDATE session_operations SET complete=1, data=? WHERE student_id=? AND offering_id=? AND operation_id=?",
                             (operation.model_dump_json(), s.student_id, s.offering_id, operation.id))
        return operation
