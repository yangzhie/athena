"""Backend memory snapshots with explicit conversation/learning separation."""

from pydantic import Field, model_validator

from ._schema import Contract, NonBlankString
from .activities import ClientCapabilities


class StoredTurn(Contract):
    user_text: NonBlankString
    assistant_text: NonBlankString


class TopicConversation(Contract):
    topic_id: NonBlankString
    goal: NonBlankString
    discussion_focus: NonBlankString | None = None
    history: list[StoredTurn] = Field(default_factory=list)


class ConversationMemory(Contract):
    capabilities: ClientCapabilities = Field(default_factory=ClientCapabilities)
    learner_id: NonBlankString
    session_id: NonBlankString
    history: list[StoredTurn] = Field(default_factory=list)
    active_topic: TopicConversation | None = None
    archived_topics: list[TopicConversation] = Field(default_factory=list)

    @model_validator(mode='after')
    def unique_topics(self):
        topics = [*self.archived_topics, *([self.active_topic] if self.active_topic else [])]
        if len({item.topic_id for item in topics}) != len(topics):
            raise ValueError('Topic IDs must be unique.')
        return self


from .assessment_models import AssessmentRecord, QuestionRecord
from .learning import LearningActivity, LearningState
from .roadmap import Roadmap
from .retrieval import RetrievalResult


class TopicLearning(Contract):
    topic_id: NonBlankString
    learning_state: LearningState
    roadmap: Roadmap | None = None
    question_records: list[QuestionRecord] = Field(default_factory=list)
    assessment_records: list[AssessmentRecord] = Field(default_factory=list)
    current_activity: LearningActivity | None = None
    knowledge: RetrievalResult | None = None


class LearningMemory(Contract):
    """Private backend snapshot: includes question keys and grading criteria."""

    learner_id: NonBlankString
    session_id: NonBlankString
    active_topic: TopicLearning | None = None
    archived_topics: list[TopicLearning] = Field(default_factory=list)

    @model_validator(mode='after')
    def unique_topics(self):
        topics = [*self.archived_topics, *([self.active_topic] if self.active_topic else [])]
        if len({item.topic_id for item in topics}) != len(topics):
            raise ValueError('Topic IDs must be unique.')
        return self
