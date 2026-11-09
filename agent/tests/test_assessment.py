import asyncio
import json
from pathlib import Path

import pytest

from athena_agent.assessment import AssessmentService
from athena_agent.context import ContextBudget, ContextBudgetError, ContextBuilder
from athena_agent.conversation import ConversationError, SessionNotFoundError
from athena_agent.llm import DependencyError, InvalidOutputError, LLMError, MockLLM
from athena_agent.reliable_llm import ReliableLLM, RetryPolicy
from .test_session_planning import planning_data, setup_planner


MC = {
    'prompt': 'Which pair should Bubble Sort swap?',
    'choices': [{'choice_id': 'a', 'text': 'An adjacent out-of-order pair'}, {'choice_id': 'b', 'text': 'Any random pair'}],
    'correct_choice_id': 'a', 'rationale': 'The algorithm compares adjacent values.',
}


@pytest.fixture
def assessed_topic(planning_data):
    context, store, _, planner = setup_planner(planning_data)
    asyncio.run(planner.plan(context))
    return context, store


def service(store, responses, **kwargs):
    mock = MockLLM(responses)
    return AssessmentService(store, ReliableLLM(mock, policy=RetryPolicy(max_attempts=1)), **kwargs), mock


def test_multiple_choice_uses_concept_and_keeps_criteria_private(assessed_topic):
    context, store = assessed_topic
    assessor, mock = service(store, [MC, MC])
    before = store.read(context)
    first = asyncio.run(assessor.generate_multiple_choice(context, 'bubble-sort'))
    second = asyncio.run(assessor.generate_multiple_choice(context, 'bubble-sort'))
    after = store.read(context)
    assert first.question.concept_id == 'bubble-sort'
    assert first.question.difficulty == 'intermediate'
    assert first.question.question_id != second.question.question_id
    assert first.activity_id != second.activity_id
    assert 'Trace a complete sorting pass.' in mock.calls[0].messages[1].content
    assert len(after.active_topic.question_records) == 2
    assert after.active_topic.question_records[0].bundle.criteria.correct_choice_id == 'a'
    for private in ['correct_choice_id', 'rationale', 'criteria']:
        assert private not in first.model_dump_json()
    assert after.active_topic.learning_state == before.active_topic.learning_state
    assert after.history == before.history
    first.question.prompt = 'Changed'
    assert store.read(context).active_topic.question_records[0].bundle.question.prompt == MC['prompt']


def test_missing_concept_roadmap_and_cross_learner_do_not_call_model(assessed_topic):
    context, store = assessed_topic
    assessor, mock = service(store, [])
    with pytest.raises(ConversationError, match='not in'):
        asyncio.run(assessor.generate_multiple_choice(context, 'missing'))
    with pytest.raises(SessionNotFoundError):
        asyncio.run(assessor.generate_multiple_choice(context.model_copy(update={'learner_id': 'other'}), 'bubble-sort'))
    other = context.model_copy(update={'session_id': 'other'})
    store.create(other)
    store.initialize_goal(other, 'Graphs')
    with pytest.raises(ConversationError, match='roadmap'):
        asyncio.run(assessor.generate_multiple_choice(other, 'graphs'))
    assert mock.calls == []


@pytest.mark.parametrize('failure', [DependencyError('Unavailable'), {**MC, 'correct_choice_id': 'missing'}, {**MC, 'prompt': ' '}])
def test_generation_failure_does_not_record_question(assessed_topic, failure):
    context, store = assessed_topic
    assessor, _ = service(store, [failure])
    before = store.read(context)
    with pytest.raises(LLMError):
        asyncio.run(assessor.generate_multiple_choice(context, 'bubble-sort'))
    assert store.read(context) == before


def test_oversized_generation_context_does_not_call_model(assessed_topic):
    context, store = assessed_topic
    assessor, mock = service(store, [], context_builder=ContextBuilder(ContextBudget(context_window=3000)))
    before = store.read(context)
    with pytest.raises(ContextBudgetError):
        asyncio.run(assessor.generate_multiple_choice(context, 'bubble-sort'))
    assert mock.calls == []
    assert store.read(context) == before


def test_cancelled_generation_does_not_save(assessed_topic):
    context, store = assessed_topic
    from unittest.mock import AsyncMock
    provider = AsyncMock()
    provider.generate.side_effect = asyncio.CancelledError()
    before = store.read(context)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(AssessmentService(store, provider).generate_multiple_choice(context, 'bubble-sort'))
    assert store.read(context) == before


def test_stale_generation_does_not_overwrite_session(assessed_topic):
    context, store = assessed_topic

    class Provider:
        async def generate(self, messages, model):
            store.update_focus(context, 'Newer focus')
            return model.model_validate(MC)

    with pytest.raises(ConversationError, match='session changed'):
        asyncio.run(AssessmentService(store, Provider()).generate_multiple_choice(context, 'bubble-sort'))
    assert store.read(context).active_topic.question_records == []
    assert store.read(context).active_topic.discussion_focus == 'Newer focus'


OPEN = {
    'prompt': 'Explain why one pass moves the largest value to the end.',
    'expected_reasoning': 'Explain each adjacent comparison and the movement of the larger value.',
}


def test_open_ended_generation_keeps_rubric_private(assessed_topic):
    context, store = assessed_topic
    assessor, mock = service(store, [OPEN])
    before = store.read(context)
    activity = asyncio.run(assessor.generate_open_ended(context, 'bubble-sort'))
    assert activity.question.kind == 'open_ended'
    assert activity.question.difficulty == 'intermediate'
    assert 'expected_reasoning' not in activity.model_dump_json()
    record = store.read(context).active_topic.question_records[0]
    assert record.bundle.criteria.expected_reasoning == OPEN['expected_reasoning']
    assert store.read(context).active_topic.learning_state == before.active_topic.learning_state
    assert 'Trace a complete sorting pass.' in mock.calls[0].messages[1].content


@pytest.mark.parametrize('kind,draft', [('multiple_choice', MC), ('open_ended', OPEN)])
def test_difficulty_override_and_invalid_override(assessed_topic, kind, draft):
    from pydantic import ValidationError
    context, store = assessed_topic
    assessor, mock = service(store, [draft])
    generate = getattr(assessor, 'generate_' + kind)
    activity = asyncio.run(generate(context, 'bubble-sort', difficulty='advanced'))
    assert activity.question.difficulty == 'advanced'
    assert '"requested_difficulty": "advanced"' in mock.calls[0].messages[1].content
    assert store.read(context).active_topic.roadmap.graph.concepts[1].difficulty == 'intermediate'
    with pytest.raises(ValidationError):
        asyncio.run(generate(context, 'bubble-sort', difficulty='expert'))
    assert len(mock.calls) == 1


def test_invalid_open_ended_criteria_do_not_save(assessed_topic):
    context, store = assessed_topic
    assessor, _ = service(store, [{**OPEN, 'expected_reasoning': ' '}])
    before = store.read(context)
    with pytest.raises(InvalidOutputError):
        asyncio.run(assessor.generate_open_ended(context, 'bubble-sort'))
    assert store.read(context) == before
