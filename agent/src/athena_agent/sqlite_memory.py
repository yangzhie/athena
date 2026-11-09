"""Durable local learning memory using atomic SQLite revision comparisons."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import sqlite3
from threading import RLock

from pydantic import ValidationError

from .contracts import RequestContext
from .conversation import ConversationError, ConversationSession, InMemoryConversationStore, SessionNotFoundError
from .memory_models import ConversationMemory, LearningMemory


class MemoryUnavailableError(ConversationError):
    code = 'dependency_unavailable'

    def __init__(self):
        super().__init__('Learning memory is temporarily unavailable.')


class SQLiteLearningMemory(InMemoryConversationStore):
    """Reuse validated domain operations; override only durable storage primitives."""

    def __init__(self, path: str | Path):
        super().__init__()
        self._db_lock = RLock()
        try:
            self._db = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False, timeout=5)
            self._db.execute('CREATE TABLE IF NOT EXISTS learning_sessions (learner_id TEXT NOT NULL, session_id TEXT NOT NULL, revision INTEGER NOT NULL, version INTEGER NOT NULL, conversation_json TEXT NOT NULL, learning_json TEXT NOT NULL, PRIMARY KEY (learner_id, session_id))')
        except sqlite3.Error:
            raise MemoryUnavailableError() from None

    def close(self):
        with self._db_lock:
            self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _encode(self, context: RequestContext, session: ConversationSession) -> tuple[str, str]:
        projection = InMemoryConversationStore()
        projection.create(context, snapshot=session)
        return projection.load_conversation(context).model_dump_json(), projection.load_learning(context).model_dump_json()

    def create(self, context: RequestContext, *, snapshot: ConversationSession | None = None) -> ConversationSession:
        key = self._key(context)
        session = ConversationSession.model_validate(snapshot.model_dump()) if snapshot is not None else ConversationSession(learner_id=key[0], session_id=key[1])
        conversation, learning = self._encode(context, session)
        try:
            with self._db_lock:
                self._db.execute('INSERT INTO learning_sessions VALUES (?, ?, ?, ?, ?, ?)', (*key, session.revision, 1, conversation, learning))
        except sqlite3.IntegrityError:
            raise ConversationError('The conversation session already exists.') from None
        except sqlite3.Error:
            raise MemoryUnavailableError() from None
        return session.model_copy(deep=True)

    def read(self, context: RequestContext) -> ConversationSession:
        key = self._key(context)
        try:
            with self._db_lock:
                row = self._db.execute('SELECT revision, version, conversation_json, learning_json FROM learning_sessions WHERE learner_id=? AND session_id=?', key).fetchone()
            if row is None:
                raise SessionNotFoundError()
            revision, version, conversation, learning = row
            if version != 1:
                raise MemoryUnavailableError()
            # The established restore operations validate identity, goals, and references.
            projection = InMemoryConversationStore()
            projection.create(context)
            projection.save_conversation(context, ConversationMemory.model_validate_json(conversation), expected_revision=0)
            projection.save_learning(context, LearningMemory.model_validate_json(learning), expected_revision=1)
            session = projection.read(context)
            session.revision = revision
            return ConversationSession.model_validate(session.model_dump())
        except SessionNotFoundError:
            raise
        except (sqlite3.Error, ValidationError, ConversationError):
            raise MemoryUnavailableError() from None

    def _save(self, context: RequestContext, session: ConversationSession) -> ConversationSession:
        session = ConversationSession.model_validate(session.model_dump())
        conversation, learning = self._encode(context, session)
        try:
            with self._db_lock:
                changed = self._db.execute('UPDATE learning_sessions SET revision=revision+1, conversation_json=?, learning_json=? WHERE learner_id=? AND session_id=? AND revision=? AND version=1', (conversation, learning, *self._key(context), session.revision)).rowcount
                if changed != 1:
                    self.read(context)
                    raise ConversationError('The session changed; retry this interaction.')
        except sqlite3.Error:
            raise MemoryUnavailableError() from None
        session.revision += 1
        return session.model_copy(deep=True)

    @asynccontextmanager
    async def creation(self, context: RequestContext):
        key = self._key(context)
        async with self._locks.setdefault(key, asyncio.Lock()):
            try:
                self.read(context)
            except SessionNotFoundError:
                yield
            else:
                raise ConversationError('The conversation session already exists.')
