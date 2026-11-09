"""In-memory conversation sessions; no persistence or transport dependency."""

import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

from pydantic import Field, model_validator

from ._schema import Contract, NonBlankString
from .contracts import RequestContext
from .llm import Message
from .learning import LearningState, LearningActivity
from .memory_models import ConversationMemory, TopicConversation
from .roadmap import Roadmap
from .assessment_models import AssessmentRecord, QuestionRecord


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
    question_records: list[QuestionRecord] = Field(default_factory=list)
    assessment_records: list[AssessmentRecord] = Field(default_factory=list)
    current_activity: LearningActivity | None = None

    @model_validator(mode='after')
    def matching_roadmap_goal(self):
        if self.roadmap is not None and self.roadmap.goal != self.learning_state.goal:
            raise ValueError('Roadmap and learning state must have the same goal.')
        questions = {record.bundle.question.question_id: record for record in self.question_records}
        if len(questions) != len(self.question_records):
            raise ValueError('Question IDs must be unique within a topic.')
        assessed_questions = set()
        assessment_ids = set()
        for record in self.assessment_records:
            assessment = record.assessment
            question = questions.get(assessment.question_id)
            if question is None or question.bundle.question.concept_id != assessment.concept_id:
                raise ValueError('Assessments must reference a recorded question and its concept.')
            if assessment.question_id in assessed_questions or assessment.assessment_id in assessment_ids:
                raise ValueError('Questions and assessment IDs cannot be assessed twice.')
            assessed_questions.add(assessment.question_id)
            assessment_ids.add(assessment.assessment_id)
        assessments_by_id = {record.assessment.assessment_id: record for record in self.assessment_records}
        followup_parents = set()
        for question in self.question_records:
            parent_id = question.parent_assessment_id
            if parent_id is None:
                continue
            parent = assessments_by_id.get(parent_id)
            if parent is None or (parent_id, question.followup_purpose) in followup_parents:
                raise ValueError('Follow-ups require a unique recorded parent and purpose.')
            if parent.assessment.concept_id != question.bundle.question.concept_id or parent.assessment.question_id == question.bundle.question.question_id:
                raise ValueError('Follow-ups must be fresh questions targeting the parent concept.')
            if question.bundle.question.kind != 'open_ended':
                raise ValueError('Verification follow-ups must ask for written reasoning.')
            followup_parents.add((parent_id, question.followup_purpose))
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

    def create(self, context: RequestContext, *, snapshot: ConversationSession | None = None) -> ConversationSession:
        key = self._key(context)
        if key in self._sessions:
            raise ConversationError('The conversation session already exists.')
        session = (ConversationSession.model_validate(snapshot.model_dump()) if snapshot is not None
                   else ConversationSession(learner_id=key[0], session_id=key[1]))
        if (session.learner_id, session.session_id) != key:
            raise ConversationError('Conversation identity cannot change.')
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


    @asynccontextmanager
    async def creation(self, context: RequestContext):
        """Serialize atomic new-session preparation without publishing partial state."""
        key = self._key(context)
        async with self._locks.setdefault(key, asyncio.Lock()):
            if key in self._sessions:
                raise ConversationError('The conversation session already exists.')
            yield


    def load_conversation(self, context: RequestContext) -> ConversationMemory:
        session = self.read(context)
        def project(topic):
            return TopicConversation(topic_id=topic.topic_id, goal=topic.learning_state.goal,
                                     discussion_focus=topic.discussion_focus,
                                     history=[turn.model_dump() for turn in topic.history])
        return ConversationMemory(
            learner_id=session.learner_id, session_id=session.session_id,
            history=[turn.model_dump() for turn in session.history],
            active_topic=project(session.active_topic) if session.active_topic else None,
            archived_topics=[project(topic) for topic in session.archived_topics],
        )

    def save_conversation(self, context: RequestContext, memory: ConversationMemory, *, expected_revision: int) -> ConversationSession:
        memory = ConversationMemory.model_validate(memory.model_dump())
        if (memory.learner_id, memory.session_id) != self._key(context):
            raise ConversationError('Conversation identity cannot change.')
        session = self.read(context)
        if type(expected_revision) is not int or session.revision != expected_revision:
            raise ConversationError('The session changed; retry this interaction.')
        existing = {topic.topic_id: topic for topic in [*session.archived_topics, *([session.active_topic] if session.active_topic else [])]}
        proposed = [*memory.archived_topics, *([memory.active_topic] if memory.active_topic else [])]
        if existing and (set(existing) != {topic.topic_id for topic in proposed} or
                         (session.active_topic.topic_id if session.active_topic else None) != (memory.active_topic.topic_id if memory.active_topic else None)):
            raise ConversationError('Conversation restore cannot replace existing learning topics.')
        def restore(data):
            topic = existing.get(data.topic_id)
            if topic is None:
                topic = TopicContext(topic_id=data.topic_id, learning_state=LearningState(goal=data.goal))
            elif topic.learning_state.goal != data.goal:
                raise ConversationError('Conversation restore cannot change the learning goal.')
            topic.history = [ConversationTurn.model_validate(turn.model_dump()) for turn in data.history]
            topic.discussion_focus = data.discussion_focus
            return topic
        session.history = [ConversationTurn.model_validate(turn.model_dump()) for turn in memory.history]
        session.active_topic = restore(memory.active_topic) if memory.active_topic else None
        session.archived_topics = [restore(topic) for topic in memory.archived_topics]
        return self._save(context, session)
