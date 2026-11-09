import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from athena_agent.assessment import AssessmentService
from athena_agent.context import ContextBudget, ContextBudgetError, ContextBuilder
from athena_agent.conversation import ConversationError, SessionNotFoundError
from athena_agent.evaluation import evaluate_teaching
from athena_agent.learning import MultipleChoiceAnswer
from athena_agent.llm import DependencyError, LLMError, MockLLM
from athena_agent.reliable_llm import ReliableLLM, RetryPolicy
from athena_agent.teaching import TeachingService
from .test_assessment import assessed_topic, MC
from .test_session_planning import planning_data


@pytest.fixture
def gap(assessed_topic):
    context, store = assessed_topic
    assessor = AssessmentService(store, MockLLM([MC]))
    question = asyncio.run(assessor.generate_multiple_choice(context, 'bubble-sort'))
    assessment = asyncio.run(assessor.evaluate(context, MultipleChoiceAnswer(question_id=question.question.question_id, selected_choice_id='b')))
    return context, store, assessment


def teaching(store, responses, **kwargs):
    mock = MockLLM(responses)
    return TeachingService(store, ReliableLLM(mock, policy=RetryPolicy(max_attempts=1)), **kwargs), mock


def test_explanation_targets_gap_without_mutation_or_private_rubric(gap):
    context, store, assessment = gap
    service, mock = teaching(store, [{'text': 'Compare adjacent values, then swap if out of order.'}])
    before = store.read(context)
    activity = asyncio.run(service.explain(context, assessment.assessment_id))
    assert activity.concept_id == 'bubble-sort'
    assert store.read(context) == before
    data = mock.calls[0].messages[1].content
    assert 'Any random pair' in data and 'Trace a complete sorting pass.' in data
    assert 'correct_choice_id' not in data and 'criteria' not in data
    assert 'one focused gap' in mock.calls[0].messages[0].content


@pytest.mark.parametrize('output', [{'text': 'word ' * 121}, {'text': 'x' * 1001}, {'text': ' '}, DependencyError('Unavailable')])
def test_invalid_or_failed_explanation_preserves_state(gap, output):
    context, store, assessment = gap
    service, _ = teaching(store, [output])
    before = store.read(context)
    with pytest.raises(LLMError):
        asyncio.run(service.explain(context, assessment.assessment_id))
    assert store.read(context) == before


def test_ownership_and_missing_evidence_checked_before_model(gap):
    context, store, assessment = gap
    service, mock = teaching(store, [])
    with pytest.raises(SessionNotFoundError):
        asyncio.run(service.explain(context.model_copy(update={'learner_id': 'other'}), assessment.assessment_id))
    with pytest.raises(ConversationError, match='assessment'):
        asyncio.run(service.explain(context, 'missing'))
    assert mock.calls == []


def test_correct_answer_is_not_a_gap(gap):
    context, store, assessment = gap
    assessor = AssessmentService(store, MockLLM([MC]))
    question = asyncio.run(assessor.generate_multiple_choice(context, 'bubble-sort'))
    correct = asyncio.run(assessor.evaluate(context, MultipleChoiceAnswer(question_id=question.question.question_id, selected_choice_id='a')))
    service, mock = teaching(store, [])
    with pytest.raises(ConversationError, match='knowledge gap'):
        asyncio.run(service.explain(context, correct.assessment_id))
    assert mock.calls == []


def test_cancellation_and_budget_overflow_preserve_state(gap):
    context, store, assessment = gap
    before = store.read(context)
    provider = AsyncMock()
    provider.generate.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(TeachingService(store, provider).explain(context, assessment.assessment_id))
    service, mock = teaching(store, [], context_builder=ContextBuilder(ContextBudget(context_window=3000)))
    with pytest.raises(ContextBudgetError):
        asyncio.run(service.explain(context, assessment.assessment_id))
    assert mock.calls == [] and store.read(context) == before


def test_stale_explanation_is_not_returned(gap):
    context, store, assessment = gap
    class Provider:
        async def generate(self, messages, model):
            store.update_focus(context, 'Changed')
            return model(text='Adjacent swaps.')
    with pytest.raises(ConversationError, match='session changed'):
        asyncio.run(TeachingService(store, Provider()).explain(context, assessment.assessment_id))


def test_repeatable_offline_evaluation():
    fixture = json.loads((Path(__file__).parent / 'fixtures/teaching.json').read_text())
    first = asyncio.run(evaluate_teaching(fixture))
    assert first['passed']
    assert first == asyncio.run(evaluate_teaching(fixture))
