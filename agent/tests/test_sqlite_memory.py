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


def test_concurrent_identical_answers_across_connections_commit_once(tmp_path):
    path = tmp_path / 'memory.sqlite'
    with SQLiteLearningMemory(path) as first, SQLiteLearningMemory(path) as second:
        question = asyncio.run(LearningOrchestrator(first, MockLLM(one_concept_responses())).start(context(), 'Comparisons'))
        answer = MultipleChoiceAnswer(question_id=question.question.question_id, selected_choice_id='a')
        original_revision = first.read(context()).revision
        async def run():
            entered = 0
            both = asyncio.Event()
            class Provider:
                async def generate(self, messages, model):
                    nonlocal entered
                    entered += 1
                    if entered == 2:
                        both.set()
                    await both.wait()
                    return model.model_validate(OPEN)
            return await asyncio.gather(LearningOrchestrator(first, Provider()).answer(context(), answer), LearningOrchestrator(second, Provider()).answer(context(), answer))
        activities = asyncio.run(run())
        assert activities[0] == activities[1]
        saved = first.read(context())
        assert saved.revision == original_revision + 1
        assert len(saved.active_topic.assessment_records) == len(saved.history) == 1
        assert len(saved.active_topic.question_records) == 2
    with SQLiteLearningMemory(path) as reopened:
        mock = MockLLM([])
        replay = asyncio.run(LearningOrchestrator(reopened, mock).answer(context(), answer))
        assert replay == activities[0] and mock.calls == []
        assert reopened.read(context()) == saved
        with pytest.raises(ConversationError, match='already has an answer'):
            asyncio.run(LearningOrchestrator(reopened, mock).answer(context(), answer.model_copy(update={'selected_choice_id': 'b'})))
        with pytest.raises(ConversationError, match='already has an answer'):
            asyncio.run(LearningOrchestrator(reopened, mock).answer(context(), answer, hint_used=True))
        assert reopened.read(context()) == saved


def test_bundled_memory_evaluation():
    import json
    from pathlib import Path
    from athena_agent.evaluation import evaluate_fixture
    fixture = json.loads((Path(__file__).parent / 'fixtures/memory_journey.json').read_text())
    assert asyncio.run(evaluate_fixture(fixture))['passed']


def test_upgrade_private_operation_receipts_are_atomic_and_not_exported(tmp_path):
    path = tmp_path / 'old-memory.sqlite'
    # A database created before host operation receipts were introduced.
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE learning_sessions (learner_id TEXT NOT NULL, session_id TEXT NOT NULL, revision INTEGER NOT NULL, version INTEGER NOT NULL, conversation_json TEXT NOT NULL, learning_json TEXT NOT NULL, PRIMARY KEY (learner_id, session_id))')
    with SQLiteLearningMemory(path) as store:
        store.create(context())
        before = store.read(context())
        updated = before.model_copy(deep=True)
        updated.operation_results['op'] = {'request': {'kind': 'message'}, 'replies': [{'content': 'Saved'}]}
        updated.history.append(ConversationTurn(user_text='Question', assistant_text='Saved'))
        with sqlite3.connect(path) as db:
            db.execute("CREATE TRIGGER fail_save BEFORE UPDATE ON learning_sessions BEGIN SELECT RAISE(ABORT, 'failed write'); END")
        with pytest.raises(MemoryUnavailableError):
            store._save(context(), updated)
        assert store.read(context()) == before
        with sqlite3.connect(path) as db:
            db.execute('DROP TRIGGER fail_save')
        saved = store._save(context(), updated)
        assert 'operation_results' not in store.load_conversation(context()).model_dump()
        assert 'operation_results' not in store.load_learning(context()).model_dump()
    with SQLiteLearningMemory(path) as store:
        assert store.read(context()) == saved
        # Unrelated conversation updates must preserve the private receipt.
        store.append_turn(context(), ConversationTurn(user_text='Next', assistant_text='Reply'))
        assert store.read(context()).operation_results == saved.operation_results
        with sqlite3.connect(path) as db:
            db.execute("UPDATE learning_sessions SET operations_json='invalid json'")
        with pytest.raises(MemoryUnavailableError):
            store.read(context())
