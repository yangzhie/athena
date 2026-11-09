"""Learning-memory boundary shared by conversation and learning services."""

from contextlib import AbstractAsyncContextManager
from typing import Protocol, runtime_checkable

from .contracts import RequestContext
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


# The established store already contains topic evidence and learning state. Reuse it.
InMemoryLearningMemory = InMemoryConversationStore
