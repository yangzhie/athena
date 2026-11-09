"""Learning-memory boundary shared by conversation and learning services."""

from contextlib import AbstractAsyncContextManager
from typing import Protocol, runtime_checkable

from .contracts import RequestContext
from .memory_models import ConversationMemory, LearningMemory
from .conversation import ConversationSession, ConversationTurn, InMemoryConversationStore


@runtime_checkable
class LearningMemoryStore(Protocol):
    """Identity-scoped snapshots and compare-and-save with whole-session atomicity.

    Implementations validate snapshots, reject identity changes/stale revisions,
    and return independent copies. Async operations serialize per learner/session
    within one adapter instance; durable adapters must also compare revisions at
    their storage transaction boundary. Snapshots are internal, with private criteria.
    """

    def create(self, context: RequestContext, *, snapshot: ConversationSession | None = None) -> ConversationSession: ...
    def read(self, context: RequestContext) -> ConversationSession: ...
    def _save(self, context: RequestContext, session: ConversationSession) -> ConversationSession: ...
    def initialize_goal(self, context: RequestContext, goal: str) -> ConversationSession: ...
    def update_focus(self, context: RequestContext, focus: str | None) -> ConversationSession: ...
    def append_turn(self, context: RequestContext, turn: ConversationTurn) -> ConversationSession: ...
    def interaction(self, context: RequestContext) -> AbstractAsyncContextManager[ConversationSession]: ...
    def creation(self, context: RequestContext) -> AbstractAsyncContextManager[None]: ...
    def load_learning(self, context: RequestContext) -> LearningMemory: ...
    def save_learning(self, context: RequestContext, memory: LearningMemory, *, expected_revision: int) -> ConversationSession: ...
    def load_conversation(self, context: RequestContext) -> ConversationMemory: ...
    def save_conversation(self, context: RequestContext, memory: ConversationMemory, *, expected_revision: int) -> ConversationSession: ...


# The established store already contains topic evidence and learning state. Reuse it.
InMemoryLearningMemory = InMemoryConversationStore


class LearnerScopedMemory:
    """Host-created adapter that rejects a context for any other learner.

    This binds an already trusted host identity; it does not authenticate users.
    All storage and transaction semantics remain in the injected implementation.
    """

    def __init__(self, store: LearningMemoryStore, learner_id: str):
        self._store = store
        self._learner_id = RequestContext(request_id='binding', learner_id=learner_id).learner_id

    def _checked(self, context: RequestContext) -> RequestContext:
        from .conversation import SessionNotFoundError
        context = RequestContext.model_validate(context.model_dump())
        if context.learner_id != self._learner_id:
            raise SessionNotFoundError()
        return context

    def create(self, context, *, snapshot=None):
        return self._store.create(self._checked(context), snapshot=snapshot)

    def read(self, context):
        return self._store.read(self._checked(context))

    def _save(self, context, session):
        return self._store._save(self._checked(context), session)

    def initialize_goal(self, context, goal):
        return self._store.initialize_goal(self._checked(context), goal)

    def update_focus(self, context, focus):
        return self._store.update_focus(self._checked(context), focus)

    def append_turn(self, context, turn):
        return self._store.append_turn(self._checked(context), turn)

    def interaction(self, context):
        return self._store.interaction(self._checked(context))

    def creation(self, context):
        return self._store.creation(self._checked(context))

    def load_conversation(self, context):
        return self._store.load_conversation(self._checked(context))

    def save_conversation(self, context, memory, *, expected_revision):
        return self._store.save_conversation(self._checked(context), memory, expected_revision=expected_revision)

    def load_learning(self, context):
        return self._store.load_learning(self._checked(context))

    def save_learning(self, context, memory, *, expected_revision):
        return self._store.save_learning(self._checked(context), memory, expected_revision=expected_revision)
