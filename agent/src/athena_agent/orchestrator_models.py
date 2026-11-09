"""Learner-facing composed orchestration results."""

from ._schema import Contract
from .conversation_manager import ConversationReply
from .learning import LearningActivity


class LearningMessageResult(Contract):
    reply: ConversationReply
    activity: LearningActivity | None = None


from .learning import FeedbackActivity, LearningState
from .progress import ProgressSummary


class LearningView(Contract):
    activity: LearningActivity | None
    learning_state: LearningState
    progress: ProgressSummary
    latest_feedback: FeedbackActivity | None = None
