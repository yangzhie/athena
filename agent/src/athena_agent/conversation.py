"""In-memory conversation sessions; no persistence or transport dependency."""

from pydantic import Field

from ._schema import Contract, NonBlankString
from .contracts import RequestContext
from .llm import Message


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


class ConversationSession(Contract):
    learner_id: NonBlankString
    session_id: NonBlankString
    history: list[ConversationTurn] = Field(default_factory=list)


class InMemoryConversationStore:
    """Single-process storage; callers receive independent snapshots."""

    def __init__(self):
        self._sessions: dict[tuple[str, str], ConversationSession] = {}

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
        session.history.append(ConversationTurn.model_validate(turn.model_dump()))
        self._sessions[self._key(context)] = session
        return session.model_copy(deep=True)
