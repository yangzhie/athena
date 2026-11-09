"""Learner-facing composed orchestration results."""

from ._schema import Contract
from .conversation_manager import ConversationReply
from .learning import LearningActivity


class LearningMessageResult(Contract):
    reply: ConversationReply
    activity: LearningActivity | None = None
