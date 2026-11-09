"""Backend memory snapshots with explicit conversation/learning separation."""

from pydantic import Field, model_validator

from ._schema import Contract, NonBlankString


class StoredTurn(Contract):
    user_text: NonBlankString
    assistant_text: NonBlankString


class TopicConversation(Contract):
    topic_id: NonBlankString
    goal: NonBlankString
    discussion_focus: NonBlankString | None = None
    history: list[StoredTurn] = Field(default_factory=list)


class ConversationMemory(Contract):
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
