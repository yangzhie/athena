"""University domain and opaque browser identities, held by the server."""
import hashlib
import json
import secrets
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Annotated, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Semester = Literal['Semester 1', 'Semester 2', 'Summer']


class CreateOffering(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{1,23}$')]
    title: Text
    year: int = Field(ge=2000, le=2100)
    semester: Semester


SCHEMA = '''
CREATE TABLE IF NOT EXISTS anonymous_identities (
    token_hash TEXT PRIMARY KEY, student_id TEXT NOT NULL UNIQUE, expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS units (code TEXT PRIMARY KEY, title TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS offerings (
    id TEXT PRIMARY KEY, code TEXT NOT NULL REFERENCES units(code),
    year INTEGER NOT NULL, semester TEXT NOT NULL, status TEXT NOT NULL,
    suggestions TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS management_grants (
    offering_id TEXT NOT NULL REFERENCES offerings(id), student_id TEXT NOT NULL,
    capability TEXT NOT NULL UNIQUE, PRIMARY KEY(offering_id, student_id)
);
CREATE TABLE IF NOT EXISTS environments (
    id TEXT PRIMARY KEY, student_id TEXT NOT NULL, offering_id TEXT NOT NULL REFERENCES offerings(id),
    UNIQUE(student_id, offering_id)
);
CREATE TABLE IF NOT EXISTS offering_topics (
    offering_id TEXT NOT NULL REFERENCES offerings(id), id TEXT NOT NULL, title TEXT NOT NULL,
    concept_id TEXT, PRIMARY KEY(offering_id, id)
);
'''


class StudySpaces:
    def __init__(self, path: str | Path):
        if str(path) != ':memory:':
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = Path(path)
        self.db = sqlite3.connect(str(path), check_same_thread=False, timeout=10)
        self.lock = threading.RLock()
        self.db.execute('PRAGMA foreign_keys=ON')
        with self.db:
            self.db.executescript(SCHEMA)

    def close(self):
        self.db.close()

    def identity(self, token: str | None) -> tuple[str, str | None]:
        now = time.time()
        with self.lock, self.db:
            if token and len(token) <= 128:
                row = self.db.execute('SELECT student_id FROM anonymous_identities WHERE token_hash=? AND expires_at>?',
                                      (hashlib.sha256(token.encode()).hexdigest(), now)).fetchone()
                if row:
                    return row[0], None
            token = secrets.token_urlsafe(32)
            student = uuid.uuid4().hex
            self.db.execute('INSERT INTO anonymous_identities VALUES (?,?,?)',
                            (hashlib.sha256(token.encode()).hexdigest(), student, now + 30 * 86400))
            return student, token

    def manages(self, student: str, offering: str) -> bool:
        with self.lock:
            return bool(self.db.execute('SELECT 1 FROM management_grants WHERE offering_id=? AND student_id=?',
                                        (offering, student)).fetchone())

    def _view(self, row, student):
        return dict(id=row[0], unit=dict(code=row[1], title=row[2]), year=row[3], semester=row[4],
                    status=row[5], suggestions=json.loads(row[6]), can_manage=self.manages(student, row[0]))

    def get(self, student: str, offering: str):
        with self.lock:
            row = self.db.execute('SELECT o.id,u.code,u.title,o.year,o.semester,o.status,o.suggestions FROM offerings o '
                                  'JOIN units u ON u.code=o.code WHERE o.id=?', (offering,)).fetchone()
            if not row or (row[5] == 'draft' and not self.manages(student, offering)):
                raise HTTPException(404, 'Offering not found or not published.')
            if row[5] == 'deleted':
                raise HTTPException(410, 'This Offering has been deleted.')
            return self._view(row, student)

    def list(self, student: str):
        with self.lock:
            rows = self.db.execute('SELECT o.id,u.code,u.title,o.year,o.semester,o.status,o.suggestions FROM offerings o '
                                   'JOIN units u ON u.code=o.code WHERE o.status="published" OR '
                                   '(o.status="draft" AND EXISTS (SELECT 1 FROM management_grants g '
                                   'WHERE g.offering_id=o.id AND g.student_id=?)) ORDER BY o.year DESC,u.code,o.id', (student,)).fetchall()
            return [self._view(row, student) for row in rows]

    def create(self, student: str, body: CreateOffering):
        offering = uuid.uuid4().hex
        with self.lock, self.db:
            existing = self.db.execute('SELECT title FROM units WHERE code=?', (body.code,)).fetchone()
            if existing and existing[0].casefold() != body.title.casefold():
                raise HTTPException(409, 'This Unit code already has a different title.')
            self.db.execute('INSERT OR IGNORE INTO units VALUES (?,?)', (body.code, body.title))
            self.db.execute('INSERT INTO offerings (id,code,year,semester,status) VALUES (?,?,?,?,?)',
                            (offering, body.code, body.year, body.semester, 'draft'))
            # A non-transferable capability granted to this trusted browser identity.
            self.db.execute('INSERT INTO management_grants VALUES (?,?,?)',
                            (offering, student, secrets.token_urlsafe(32)))
        return self.get(student, offering)

    def require_manager(self, student: str, offering: str):
        self.get(student, offering)
        if not self.manages(student, offering):
            raise HTTPException(403, 'Only this study space’s creator can manage it.')

    def publish(self, student: str, offering: str):
        self.require_manager(student, offering)
        with self.lock, self.db:
            self.db.execute('UPDATE offerings SET status="published" WHERE id=?', (offering,))
        return self.get(student, offering)

    def delete(self, student: str, offering: str):
        self.require_manager(student, offering)
        with self.lock, self.db:
            self.db.execute('UPDATE offerings SET status="deleted" WHERE id=?', (offering,))

    def environment(self, student: str, offering: str) -> str:
        view = self.get(student, offering)
        if view['status'] != 'published':
            raise HTTPException(409, 'Publish this study space before starting to learn.')
        with self.lock, self.db:
            self.db.execute('INSERT OR IGNORE INTO environments VALUES (?,?,?)', (uuid.uuid4().hex, student, offering))
            return self.db.execute('SELECT id FROM environments WHERE student_id=? AND offering_id=?',
                                   (student, offering)).fetchone()[0]
