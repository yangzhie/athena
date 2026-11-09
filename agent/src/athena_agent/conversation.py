"""In-memory conversation sessions; no persistence or transport dependency."""

import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

from pydantic import Field, model_validator

from ._schema import Contract, NonBlankString
from .contracts import RequestContext
from .llm import Message
from .learning import LearningState
from .roadmap import Roadmap


class ConversationError(Exception):
    code = 'invalid_request'


class SessionNotFoundError(ConversationError):
    code = 'session_not_found'

    def __init__(self):
        super().__init__('The conversation session is unavailable.')


class ConversationTurn(Contract):
    user_text: NonBlankString
    assistant_text: NonBlankString

    def messages(self) -> list[Message]:
        return [Message(role='user', content=self.user_text), Message(role='assistant', content=self.assistant_text)]


class TopicContext(Contract):
    topic_id: NonBlankString = Field(default_factory=lambda: str(uuid4()))
    learning_state: LearningState
    discussion_focus: NonBlankString | None = None
    history: list[ConversationTurn] = Field(default_factory=list)
    roadmap: Roadmap | None = None

    @model_validator(mode='after')
    def matching_roadmap_goal(self):
        if self.roadmap is not None and self.roadmap.goal != self.learning_state.goal:
            raise ValueError('Roadmap and learning state must have the same goal.')
        return self


class ConversationSession(Contract):
    learner_id: NonBlankString
    session_id: NonBlankString
    history: list[ConversationTurn] = Field(default_factory=list)
    active_topic: TopicContext | None = None
    archived_topics: list[TopicContext] = Field(default_factory=list)
    revision: int = Field(default=0, ge=0)


class InMemoryConversationStore:
    """Single-process storage; callers receive independent snapshots."""

    def __init__(self):
        self._sessions: dict[tuple[str, str], ConversationSession] = {}
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}

    def _key(self, context: RequestContext) -> tuple[str, str]:
        if context.session_id is None:
            raise ConversationError('A session ID is required.')
        return context.learner_id, context.session_id

    def create(self, context: RequestContext) -> ConversationSession:
        key = self._key(context)
        if key in self._sessions:
            raise ConversationError('The conversation session already exists.')
        session = ConversationSession(learner_id=key[0], session_id=key[1])
        self._sessions[key] = session
        return session.model_copy(deep=True)

    def read(self, context: RequestContext) -> ConversationSession:
        session = self._sessions.get(self._key(context))
        if session is None:
            raise SessionNotFoundError()
        return session.model_copy(deep=True)

    def append_turn(self, context: RequestContext, turn: ConversationTurn) -> ConversationSession:
        session = self.read(context)
        validated = ConversationTurn.model_validate(turn.model_dump())
        session.history.append(validated)
        if session.active_topic is not None:
            session.active_topic.history.append(validated.model_copy(deep=True))
        return self._save(context, session)

    def _save(self, context: RequestContext, session: ConversationSession) -> ConversationSession:
        current = self.read(context)
        if (session.learner_id, session.session_id) != self._key(context):
            raise ConversationError('Conversation identity cannot change.')
        if current.revision != session.revision:
            raise ConversationError('The session changed; retry this interaction.')
        validated = ConversationSession.model_validate(session.model_dump())
        validated.revision += 1
        self._sessions[self._key(context)] = validated
        return validated.model_copy(deep=True)

    def initialize_goal(self, context: RequestContext, goal: str) -> ConversationSession:
        session = self.read(context)
        if session.active_topic is not None:
            raise ConversationError('The session already has an active learning goal.')
        session.active_topic = TopicContext(learning_state=LearningState(goal=goal))
        return self._save(context, session)

    def update_focus(self, context: RequestContext, focus: str | None) -> ConversationSession:
        session = self.read(context)
        if session.active_topic is None:
            raise ConversationError('Initialize a learning goal first.')
        session.active_topic.discussion_focus = focus
        return self._save(context, session)

    @asynccontextmanager
    async def interaction(self, context: RequestContext):
        """Serialise async interactions across managers sharing this store."""
        self.read(context)
        key = self._key(context)
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            yield self.read(context)
