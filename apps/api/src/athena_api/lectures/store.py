import sqlite3
import threading
from pathlib import Path
from typing import Protocol

from .models import Lecture


class LectureStore(Protocol):
    def list(self, offering_id: str) -> list[Lecture]: ...
    def get(self, offering_id: str, lecture_id: str) -> Lecture | None: ...
    def put(self, lecture: Lecture) -> None: ...


class MemoryLectureStore:
    def __init__(self) -> None:
        self.lectures: dict[str, Lecture] = {}

    def list(self, offering_id):
        return sorted((l for l in self.lectures.values() if l.offering_id == offering_id), key=lambda l: (-(l.week or 0), l.id))

    def get(self, offering_id, lecture_id):
        l = self.lectures.get(lecture_id)
        return l if l and l.offering_id == offering_id else None

    def put(self, lecture):
        self.lectures[lecture.id] = lecture


class SqliteLectureStore:
    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._db:
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS lectures (id TEXT PRIMARY KEY, offering_id TEXT NOT NULL, data TEXT NOT NULL)"
            )

    def close(self) -> None:
        self._db.close()

    def list(self, offering_id):
        with self._lock:
            rows = self._db.execute("SELECT data FROM lectures WHERE offering_id = ?", (offering_id,)).fetchall()
        out = [Lecture.model_validate_json(r[0]) for r in rows]
        return sorted(out, key=lambda l: (-(l.week or 0), l.id))

    def get(self, offering_id, lecture_id):
        with self._lock:
            row = self._db.execute(
                "SELECT data FROM lectures WHERE id = ? AND offering_id = ?", (lecture_id, offering_id)
            ).fetchone()
        return Lecture.model_validate_json(row[0]) if row else None

    def put(self, lecture):
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO lectures (id, offering_id, data) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET offering_id = excluded.offering_id, data = excluded.data",
                (lecture.id, lecture.offering_id, lecture.model_dump_json()),
            )
