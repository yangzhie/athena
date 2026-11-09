import asyncio
from unittest.mock import AsyncMock

import pytest

from athena_agent.conversation import ConversationError, InMemoryConversationStore, SessionNotFoundError
from athena_agent.contracts import RequestContext
from athena_agent.llm import DependencyError, MockLLM, LLMError
from athena_agent.orchestrator import LearningOrchestrator
from athena_agent.reliable_llm import ReliableLLM, RetryPolicy
from .test_assessment import MC
from .test_session_planning import planning_data


def setup(responses):
    store = InMemoryConversationStore()
    context = RequestContext(request_id='r', learner_id='learner', session_id='session')
    mock = MockLLM(responses)
    orchestrator = LearningOrchestrator(store, ReliableLLM(mock, policy=RetryPolicy(max_attempts=1)))
    return context, store, mock, orchestrator


@pytest.mark.parametrize('scope', ['narrow', 'broad'])
@pytest.mark.parametrize('difficulty', ['beginner', 'advanced'])
def test_start_proactively_diagnoses_without_assuming_mastery(planning_data, scope, difficulty):
    planning_data[0]['scope'] = scope
    planning_data[1]['partial_coverage'] = scope == 'broad'
    context, store, mock, orchestrator = setup([*planning_data, MC])
    activity = asyncio.run(orchestrator.start(context, 'Bubble Sort', difficulty=difficulty))
    topic = store.read(context).active_topic
    assert activity.question.concept_id == 'comparison'  # prerequisite first
    assert activity.question.difficulty == difficulty
    assert topic.current_activity == activity
    assert topic.learning_state.phase == 'diagnose' and topic.learning_state.mastery == []
    assert topic.roadmap.scope.scope == scope
    assert len(mock.calls) == 4
    assert 'criteria' not in activity.model_dump_json()
    with pytest.raises(ConversationError, match='already exists'):
        asyncio.run(orchestrator.start(context, 'Other goal'))
    assert len(mock.calls) == 4


@pytest.mark.parametrize('failure_at', range(4))
def test_failed_start_can_retry_without_partial_session(planning_data, failure_at):
    context, store, _, orchestrator = setup([*planning_data[:failure_at], DependencyError('Unavailable')])
    with pytest.raises(LLMError):
        asyncio.run(orchestrator.start(context, 'Bubble Sort'))
    with pytest.raises(SessionNotFoundError):
        store.read(context)
    retry = LearningOrchestrator(store, MockLLM([*planning_data, MC]))
    assert asyncio.run(retry.start(context, 'Bubble Sort')).kind == 'question'


def test_cancelled_start_does_not_publish_session():
    context, store, _, _ = setup([])
    provider = AsyncMock()
    provider.generate.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(LearningOrchestrator(store, provider).start(context, 'Bubble Sort'))
    with pytest.raises(SessionNotFoundError):
        store.read(context)


def test_concurrent_starts_publish_one_session(planning_data):
    context, store, mock, orchestrator = setup([*planning_data, MC])
    async def run():
        return await asyncio.gather(orchestrator.start(context, 'Bubble Sort'), orchestrator.start(context, 'Bubble Sort'), return_exceptions=True)
    results = asyncio.run(run())
    assert sum(isinstance(result, ConversationError) for result in results) == 1
    assert len(store.read(context).active_topic.question_records) == 1
    assert len(mock.calls) == 4


def test_start_evaluation_scenarios_are_repeatable():
    import json
    from pathlib import Path
    from athena_agent.evaluation import evaluate_fixture
    fixture = json.loads((Path(__file__).parent / 'fixtures/session_start.json').read_text())
    first = asyncio.run(evaluate_fixture(fixture))
    assert first['passed'] and len(first['results']) == 4
    assert first == asyncio.run(evaluate_fixture(fixture))
