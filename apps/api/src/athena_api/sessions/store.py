"""Storage for sessions and messages. Every method takes the student id and filters by it."""

import sqlite3
import threading
from pathlib import Path
from typing import Protocol

from .models import LearningSession, Message


class SessionStore(Protocol):
    def list(self, student_id: str, offering_id: str) -> list[LearningSession]: ...
    def get(self, student_id: str, session_id: str) -> LearningSession | None: ...
    def put(self, session: LearningSession) -> None: ...
    def delete(self, student_id: str, session_id: str) -> bool: ...
    def messages(self, student_id: str, session_id: str) -> list[Message]: ...
    def add_message(self, student_id: str, message: Message) -> None: ...
    def shared(self, offering_id: str) -> list[LearningSession]:
        """Sessions currently shared in an offering (for its lecturers)."""
        ...


class MemorySessionStore:
    def __init__(self) -> None:
        self.sessions: dict[str, LearningSession] = {}
        self.msgs: dict[str, list[Message]] = {}

    def list(self, student_id, offering_id):
        out = [s for s in self.sessions.values() if s.student_id == student_id and s.offering_id == offering_id]
        return sorted(out, key=lambda s: s.updated_at, reverse=True)

    def get(self, student_id, session_id):
        s = self.sessions.get(session_id)
        return s if s and s.student_id == student_id else None

    def put(self, session):
        self.sessions[session.id] = session

    def delete(self, student_id, session_id):
        if not self.get(student_id, session_id):
            return False
        del self.sessions[session_id]
        self.msgs.pop(session_id, None)
        return True

    def messages(self, student_id, session_id):
        return list(self.msgs.get(session_id, [])) if self.get(student_id, session_id) else []

    def add_message(self, student_id, message):
        if self.get(student_id, message.session_id):
            self.msgs.setdefault(message.session_id, []).append(message)

    def shared(self, offering_id):
        return [s for s in self.sessions.values() if s.offering_id == offering_id and s.shared and s.share_token]


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
"""


class SqliteSessionStore:
    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.Lock()
        with self._lock, self._db:
            self._db.executescript(_SCHEMA)

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

    def delete(self, student_id, session_id):
        with self._lock, self._db:
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
