"""Storage for banks, cards, attempts and review logs.

`SrsStore` is the boundary: SQLite for the PoC, Postgres later (design doc),
an in-memory store for tests. Every student-data method takes the student id,
and implementations must filter by it: one student never reads another's data.
"""

import sqlite3
import json
import copy
import time
from fastapi.encoders import jsonable_encoder
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from .models import Bank, CardState, ReviewLogEntry


@dataclass(frozen=True)
class Attempt:
    """An answered question waiting for (or holding) its rating."""

    id: str
    student_id: str
    offering_id: str
    item_id: str
    variant_id: str
    correct: bool | None
    created_at: datetime
    rated: bool = False


class CommandConflict(ValueError):
    pass


class SrsStore(Protocol):
    def command(self, student_id, offering_id, operation_id, payload, action): ...
    def get_command(self, student_id, offering_id, operation_id): ...
    def pending_attempt(self, student_id, offering_id): ...
    def get_bank(self, offering_id: str) -> Bank | None: ...
    def put_bank(self, bank: Bank) -> None: ...

    def get_card(self, student_id: str, item_id: str) -> CardState | None: ...
    def put_card(self, card: CardState, offering_id: str, created_at: datetime) -> None:
        """Insert or update. `created_at` is only stored on insert (it counts new items per day)."""
        ...
    def list_cards(self, student_id: str, offering_id: str) -> list[CardState]: ...
    def count_cards_created_since(self, student_id: str, offering_id: str, since: datetime) -> int: ...

    def add_attempt(self, attempt: Attempt) -> None: ...
    def get_attempt(self, student_id: str, attempt_id: str) -> Attempt | None: ...
    def mark_attempt_rated(self, student_id: str, attempt_id: str) -> None: ...

    def add_log(self, log: ReviewLogEntry, offering_id: str) -> None: ...
    def count_logs_since(self, student_id: str, offering_id: str, since: datetime) -> int: ...


class MemoryStore:
    """For tests."""

    def __init__(self) -> None:
        self.banks: dict[str, Bank] = {}
        self.cards: dict[tuple[str, str], tuple[CardState, str, datetime]] = {}
        self.attempts: dict[str, Attempt] = {}
        self.logs: list[tuple[ReviewLogEntry, str]] = []
        self.receipts = {}
        self._lock = threading.RLock()

    def command(self, student_id, offering_id, operation_id, payload, action):
        try:
            signature = json.dumps(payload, sort_keys=True, allow_nan=False)
        except ValueError:
            raise CommandConflict('Practice input must be finite JSON data.') from None
        key = (student_id, offering_id, operation_id)
        with self._lock:
            previous = self.receipts.get(key) if operation_id else None
            if previous:
                if previous[0] != signature:
                    raise CommandConflict('Practice operation identifier was reused with different input.')
                return copy.deepcopy(previous[1])
            backup = copy.deepcopy((self.banks, self.cards, self.attempts, self.logs, self.receipts))
            try:
                result = action()
                if operation_id:
                    self.receipts[key] = (signature, jsonable_encoder(result), time.time())
                return result
            except BaseException:
                self.banks, self.cards, self.attempts, self.logs, self.receipts = backup
                raise

    def get_command(self, student_id, offering_id, operation_id):
        with self._lock:
            row = self.receipts.get((student_id, offering_id, operation_id))
            return (json.loads(row[0]), copy.deepcopy(row[1])) if row else None

    def pending_attempt(self, student_id, offering_id):
        with self._lock:
            pending = [attempt for attempt in self.attempts.values() if attempt.student_id == student_id and attempt.offering_id == offering_id and not attempt.rated]
            return max(pending, key=lambda attempt: (attempt.created_at, attempt.id)) if pending else None

    def get_bank(self, offering_id):
        return self.banks.get(offering_id)

    def put_bank(self, bank):
        self.banks[bank.offering_id] = bank

    def get_card(self, student_id, item_id):
        row = self.cards.get((student_id, item_id))
        return row[0] if row else None

    def put_card(self, card, offering_id, created_at):
        existing = self.cards.get((card.student_id, card.item_id))
        self.cards[(card.student_id, card.item_id)] = (card, offering_id, existing[2] if existing else created_at)

    def list_cards(self, student_id, offering_id):
        return [c for (s, _), (c, o, _) in self.cards.items() if s == student_id and o == offering_id]

    def count_cards_created_since(self, student_id, offering_id, since):
        return sum(1 for (s, _), (_, o, t) in self.cards.items() if s == student_id and o == offering_id and t >= since)

    def add_attempt(self, attempt):
        self.attempts[attempt.id] = attempt

    def get_attempt(self, student_id, attempt_id):
        a = self.attempts.get(attempt_id)
        return a if a and a.student_id == student_id else None

    def mark_attempt_rated(self, student_id, attempt_id):
        a = self.get_attempt(student_id, attempt_id)
        if a:
            self.attempts[attempt_id] = Attempt(**{**a.__dict__, "rated": True})

    def add_log(self, log, offering_id):
        self.logs.append((log, offering_id))

    def count_logs_since(self, student_id, offering_id, since):
        return sum(1 for l, o in self.logs if l.student_id == student_id and o == offering_id and l.reviewed_at >= since)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS banks (
    offering_id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cards (
    student_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    offering_id TEXT NOT NULL,
    data TEXT NOT NULL,
    due TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (student_id, item_id)
);
CREATE INDEX IF NOT EXISTS cards_by_student ON cards (student_id, offering_id, due);
CREATE TABLE IF NOT EXISTS attempts (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    offering_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    variant_id TEXT NOT NULL,
    correct INTEGER,
    created_at TEXT NOT NULL,
    rated INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS review_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    offering_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    reviewed_at TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS srs_commands (
 student_id TEXT NOT NULL, offering_id TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL, result TEXT NOT NULL, created_at REAL NOT NULL,
 PRIMARY KEY(student_id,offering_id,id)
);
CREATE INDEX IF NOT EXISTS logs_by_student ON review_logs (student_id, offering_id, reviewed_at);
"""


def _iso(t: datetime) -> str:
    return t.isoformat()


class SqliteStore:
    """Single-file SQLite store. Timestamps are stored as UTC ISO strings, which sort correctly."""

    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.RLock()
        self._local = threading.local()
        with self._lock, self._db:
            self._db.executescript(_SCHEMA)
            if 'created_at' not in {r[1] for r in self._db.execute('PRAGMA table_info(srs_commands)')}:
                self._db.execute('ALTER TABLE srs_commands ADD COLUMN created_at REAL NOT NULL DEFAULT 0')

    def command(self, student_id, offering_id, operation_id, payload, action):
        try:
            signature = json.dumps(payload, sort_keys=True, allow_nan=False)
        except ValueError:
            raise CommandConflict('Practice input must be finite JSON data.') from None
        with self._lock:
            try:
                self._db.execute('BEGIN IMMEDIATE')
                if operation_id:
                    previous = self._db.execute('SELECT payload,result FROM srs_commands WHERE student_id=? AND offering_id=? AND id=?',
                                                (student_id, offering_id, operation_id)).fetchone()
                    if previous:
                        if previous[0] != signature:
                            raise CommandConflict('Practice operation identifier was reused with different input.')
                        self._db.commit()
                        return json.loads(previous[1])
                self._local.in_command = True
                result = action()
                if operation_id:
                    self._db.execute('INSERT INTO srs_commands VALUES (?,?,?,?,?,?)',
                                      (student_id, offering_id, operation_id, signature, json.dumps(jsonable_encoder(result)), time.time()))
                self._db.commit()
                return result
            except BaseException:
                self._db.rollback()
                raise
            finally:
                self._local.in_command = False

    def get_command(self, student_id, offering_id, operation_id):
        row = self._one('SELECT payload,result FROM srs_commands WHERE student_id=? AND offering_id=? AND id=?',
                        (student_id, offering_id, operation_id))
        return (json.loads(row[0]), json.loads(row[1])) if row else None

    def pending_attempt(self, student_id, offering_id):
        row = self._one('SELECT id FROM attempts WHERE student_id=? AND offering_id=? AND rated=0 ORDER BY created_at DESC,id DESC LIMIT 1', (student_id, offering_id))
        return self.get_attempt(student_id, row[0]) if row else None

    def close(self) -> None:
        self._db.close()

    def _one(self, sql: str, args: tuple):
        with self._lock:
            return self._db.execute(sql, args).fetchone()

    def _all(self, sql: str, args: tuple):
        with self._lock:
            return self._db.execute(sql, args).fetchall()

    def _write(self, sql: str, args: tuple) -> None:
        with self._lock:
            if getattr(self._local, 'in_command', False):
                self._db.execute(sql, args)
            else:
                with self._db:
                    self._db.execute(sql, args)

    def get_bank(self, offering_id):
        row = self._one("SELECT data FROM banks WHERE offering_id = ?", (offering_id,))
        return Bank.model_validate_json(row[0]) if row else None

    def put_bank(self, bank):
        self._write(
            "INSERT INTO banks (offering_id, data) VALUES (?, ?) ON CONFLICT(offering_id) DO UPDATE SET data = excluded.data",
            (bank.offering_id, bank.model_dump_json()),
        )

    def get_card(self, student_id, item_id):
        row = self._one("SELECT data FROM cards WHERE student_id = ? AND item_id = ?", (student_id, item_id))
        return CardState.model_validate_json(row[0]) if row else None

    def put_card(self, card, offering_id, created_at):
        self._write(
            """INSERT INTO cards (student_id, item_id, offering_id, data, due, created_at) VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(student_id, item_id) DO UPDATE SET data = excluded.data, due = excluded.due""",
            (card.student_id, card.item_id, offering_id, card.model_dump_json(), _iso(card.due), _iso(created_at)),
        )

    def list_cards(self, student_id, offering_id):
        rows = self._all("SELECT data FROM cards WHERE student_id = ? AND offering_id = ? ORDER BY due", (student_id, offering_id))
        return [CardState.model_validate_json(r[0]) for r in rows]

    def count_cards_created_since(self, student_id, offering_id, since):
        row = self._one(
            "SELECT COUNT(*) FROM cards WHERE student_id = ? AND offering_id = ? AND created_at >= ?",
            (student_id, offering_id, _iso(since)),
        )
        return row[0]

    def add_attempt(self, a):
        self._write(
            "INSERT INTO attempts (id, student_id, offering_id, item_id, variant_id, correct, created_at, rated) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (a.id, a.student_id, a.offering_id, a.item_id, a.variant_id, None if a.correct is None else int(a.correct), _iso(a.created_at), int(a.rated)),
        )

    def get_attempt(self, student_id, attempt_id):
        row = self._one(
            "SELECT id, student_id, offering_id, item_id, variant_id, correct, created_at, rated FROM attempts WHERE id = ? AND student_id = ?",
            (attempt_id, student_id),
        )
        if not row:
            return None
        return Attempt(
            id=row[0], student_id=row[1], offering_id=row[2], item_id=row[3], variant_id=row[4],
            correct=None if row[5] is None else bool(row[5]),
            created_at=datetime.fromisoformat(row[6]), rated=bool(row[7]),
        )

    def mark_attempt_rated(self, student_id, attempt_id):
        self._write("UPDATE attempts SET rated = 1 WHERE id = ? AND student_id = ?", (attempt_id, student_id))

    def add_log(self, log, offering_id):
        self._write(
            "INSERT INTO review_logs (student_id, offering_id, item_id, reviewed_at, data) VALUES (?, ?, ?, ?, ?)",
            (log.student_id, offering_id, log.item_id, _iso(log.reviewed_at), log.model_dump_json()),
        )

    def count_logs_since(self, student_id, offering_id, since):
        row = self._one(
            "SELECT COUNT(*) FROM review_logs WHERE student_id = ? AND offering_id = ? AND reviewed_at >= ?",
            (student_id, offering_id, _iso(since)),
        )
        return row[0]

