import asyncio
import sqlite3

import pytest

from athena_agent.contracts import RequestContext
from athena_agent.conversation import ConversationError, ConversationTurn, SessionNotFoundError
from athena_agent.learning import MultipleChoiceAnswer
from athena_agent.llm import MockLLM
from athena_agent.memory import LearningMemoryStore
from athena_agent.orchestrator import LearningOrchestrator
from athena_agent.sqlite_memory import MemoryUnavailableError, SQLiteLearningMemory
from .test_orchestrator import one_concept_responses, OPEN


def context():
    return RequestContext(request_id='r', learner_id='l', session_id='s')


def test_reopen_resumes_current_activity_and_continues_evidence(tmp_path):
    path = tmp_path / 'memory.sqlite'
    with SQLiteLearningMemory(path) as store:
        assert isinstance(store, LearningMemoryStore)
        question = asyncio.run(LearningOrchestrator(store, MockLLM(one_concept_responses())).start(context(), 'Comparisons'))
        before = store.read(context())
    with SQLiteLearningMemory(path) as store:
        orchestrator = LearningOrchestrator(store, MockLLM([OPEN]))
        assert store.read(context()) == before
        assert orchestrator.resume(context()) == question
        followup = asyncio.run(orchestrator.answer(context(), MultipleChoiceAnswer(question_id=question.question.question_id, selected_choice_id='a')))
        assert followup.question.kind == 'open_ended'
    with SQLiteLearningMemory(path) as store:
        assert len(store.read(context()).active_topic.assessment_records) == 1
        assert len(store.load_conversation(context()).history) == 1
        assert store.load_learning(context()).active_topic.learning_state.mastery[0].status == 'developing'


def test_separate_connections_compare_revision_without_overwriting(tmp_path):
    path = tmp_path / 'memory.sqlite'
    with SQLiteLearningMemory(path) as first, SQLiteLearningMemory(path) as second:
        first.create(context())
        stale = second.read(context())
        first.append_turn(context(), ConversationTurn(user_text='First', assistant_text='Saved'))
        with pytest.raises(ConversationError, match='session changed'):
            second._save(context(), stale)
        assert second.read(context()) == first.read(context())
        with pytest.raises(ConversationError, match='already exists'):
            second.create(context())
        with pytest.raises(SessionNotFoundError):
            second.read(context().model_copy(update={'learner_id': 'foreign'}))


def test_database_stores_separate_projections_and_handles_closed_store(tmp_path):
    path = tmp_path / 'memory.sqlite'
    store = SQLiteLearningMemory(path)
    asyncio.run(LearningOrchestrator(store, MockLLM(one_concept_responses())).start(context(), 'Comparisons'))
    with sqlite3.connect(path) as db:
        conversation, learning = db.execute('SELECT conversation_json, learning_json FROM learning_sessions').fetchone()
        assert 'question_records' not in conversation and 'history' not in learning
    store.close()
    with pytest.raises(MemoryUnavailableError):
        store.read(context())


def test_failed_answer_reopens_at_unchanged_question(tmp_path):
    from athena_agent.llm import DependencyError, LLMError
    from athena_agent.reliable_llm import ReliableLLM, RetryPolicy
    path = tmp_path / 'memory.sqlite'
    with SQLiteLearningMemory(path) as store:
        question = asyncio.run(LearningOrchestrator(store, MockLLM(one_concept_responses())).start(context(), 'Comparisons'))
        before = store.read(context())
        failing = LearningOrchestrator(store, ReliableLLM(MockLLM([DependencyError('Unavailable')]), policy=RetryPolicy(max_attempts=1)))
        with pytest.raises(LLMError):
            asyncio.run(failing.answer(context(), MultipleChoiceAnswer(question_id=question.question.question_id, selected_choice_id='a')))
    with SQLiteLearningMemory(path) as store:
        assert store.read(context()) == before
        assert LearningOrchestrator(store, MockLLM([])).resume(context()) == question
