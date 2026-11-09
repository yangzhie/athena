import asyncio

import pytest

from athena_agent.contracts import RequestContext
from athena_agent.conversation import ConversationError, ConversationTurn, InMemoryConversationStore, SessionNotFoundError
from athena_agent.memory import InMemoryLearningMemory, LearningMemoryStore
from athena_agent.llm import MockLLM
from athena_agent.orchestrator import LearningOrchestrator
from .test_orchestrator import one_concept_responses


def test_in_memory_learning_memory_reuses_existing_implementation():
    assert InMemoryLearningMemory is InMemoryConversationStore
    store = InMemoryLearningMemory()
    assert isinstance(store, LearningMemoryStore)
    context = RequestContext(request_id='r', learner_id='l', session_id='s')
    activity = asyncio.run(LearningOrchestrator(store, MockLLM(one_concept_responses())).start(context, 'Compare'))
    snapshot = store.read(context)
    assert snapshot.active_topic.current_activity == activity
    snapshot.active_topic.learning_state.goal = 'Changed'
    assert store.read(context).active_topic.learning_state.goal == 'Compare'


def test_memory_contract_rejects_stale_and_foreign_snapshots():
    store = InMemoryLearningMemory()
    context = RequestContext(request_id='r', learner_id='l', session_id='s')
    store.create(context)
    stale = store.read(context)
    store.append_turn(context, ConversationTurn(user_text='Hello', assistant_text='Ready'))
    with pytest.raises(ConversationError, match='session changed'):
        store._save(context, stale)
    other = context.model_copy(update={'learner_id': 'other'})
    with pytest.raises(SessionNotFoundError):
        store.read(other)
    with pytest.raises(ConversationError, match='identity'):
        store.create(other, snapshot=store.read(context))
