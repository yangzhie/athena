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


def test_conversation_export_restores_history_goal_and_focus_without_evidence():
    context = RequestContext(request_id='r', learner_id='l', session_id='s')
    source = InMemoryLearningMemory()
    asyncio.run(LearningOrchestrator(source, MockLLM(one_concept_responses())).start(context, 'Compare'))
    source.append_turn(context, ConversationTurn(user_text='Why?', assistant_text='Compare values.'))
    source.update_focus(context, 'Relative values')
    exported = source.load_conversation(context)
    assert 'question_records' not in exported.model_dump_json()
    restored = InMemoryLearningMemory()
    restored.create(context)
    restored.save_conversation(context, exported, expected_revision=0)
    assert restored.load_conversation(context) == exported
    assert restored.read(context).active_topic.roadmap is None
    exported.active_topic.discussion_focus = 'Mutated'
    assert restored.read(context).active_topic.discussion_focus == 'Relative values'


def test_conversation_save_preserves_learning_and_rejects_stale_foreign_or_retargeted_data():
    context = RequestContext(request_id='r', learner_id='l', session_id='s')
    store = InMemoryLearningMemory()
    asyncio.run(LearningOrchestrator(store, MockLLM(one_concept_responses())).start(context, 'Compare'))
    before = store.read(context)
    exported = store.load_conversation(context)
    exported.active_topic.discussion_focus = 'New focus'
    store.save_conversation(context, exported, expected_revision=before.revision)
    assert store.read(context).active_topic.question_records == before.active_topic.question_records
    snapshot = store.read(context)
    with pytest.raises(ConversationError, match='session changed'):
        store.save_conversation(context, exported, expected_revision=before.revision)
    exported.learner_id = 'other'
    with pytest.raises(ConversationError, match='identity'):
        store.save_conversation(context, exported, expected_revision=snapshot.revision)
    exported.learner_id = context.learner_id
    exported.active_topic.goal = 'Unrelated'
    with pytest.raises(ConversationError, match='goal'):
        store.save_conversation(context, exported, expected_revision=snapshot.revision)
    assert store.read(context) == snapshot


def test_separate_learning_restore_retains_evidence_mastery_and_conversation():
    from athena_agent.learning import MultipleChoiceAnswer
    context = RequestContext(request_id='r', learner_id='l', session_id='s')
    source = InMemoryLearningMemory()
    orchestrator = LearningOrchestrator(source, MockLLM([*one_concept_responses(),
        {'misconceptions': [{'description': 'Random pairs', 'status': 'suspected', 'evidence_quote': 'Any random pair', 'confidence': 0.6}], 'prerequisite_gaps': []},
        {'text': 'Compare adjacent pairs.'},
    ]))
    question = asyncio.run(orchestrator.start(context, 'Compare'))
    asyncio.run(orchestrator.answer(context, MultipleChoiceAnswer(question_id=question.question.question_id, selected_choice_id='b')))
    conversation = source.load_conversation(context)
    learning = source.load_learning(context)
    assert 'history' not in learning.model_dump_json()
    restored = InMemoryLearningMemory()
    restored.create(context)
    restored.save_conversation(context, conversation, expected_revision=0)
    restored.save_learning(context, learning, expected_revision=restored.read(context).revision)
    assert restored.load_conversation(context) == conversation
    assert restored.load_learning(context) == learning
    assert restored.read(context).active_topic.learning_state.mastery[0].status == 'developing'
    assert restored.read(context).active_topic.assessment_records[0].diagnosis.misconceptions[0].status == 'suspected'


def test_invalid_learning_references_fail_atomically():
    from pydantic import ValidationError
    context = RequestContext(request_id='r', learner_id='l', session_id='s')
    store = InMemoryLearningMemory()
    asyncio.run(LearningOrchestrator(store, MockLLM(one_concept_responses())).start(context, 'Compare'))
    memory = store.load_learning(context)
    before = store.read(context)
    memory.active_topic.question_records[0].parent_assessment_id = 'missing'
    with pytest.raises(ValidationError):
        store.save_learning(context, memory, expected_revision=before.revision)
    assert store.read(context) == before
