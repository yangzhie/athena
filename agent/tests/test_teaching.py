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


def test_practical_example_uses_gap_and_requests_worked_steps(gap):
    context, store, assessment = gap
    service, mock = teaching(store, [{'text': 'For [3, 1], compare neighbours: 3 > 1, so swap to [1, 3].'}])
    before = store.read(context)
    activity = asyncio.run(service.example(context, assessment.assessment_id))
    assert activity.kind == 'explanation' and activity.concept_id == 'bubble-sort'
    assert 'worked steps' in mock.calls[0].messages[0].content
    assert store.read(context) == before


def test_hint_targets_unanswered_question_without_private_key(gap):
    context, store, _ = gap
    assessor = AssessmentService(store, MockLLM([MC]))
    question = asyncio.run(assessor.generate_multiple_choice(context, 'bubble-sort'))
    service, mock = teaching(store, [{'text': 'Think about which values are neighbours.'}])
    before = store.read(context)
    hint = asyncio.run(service.hint(context, question.question.question_id))
    assert hint.kind == 'hint' and hint.question_id == question.question.question_id
    data = mock.calls[0].messages[1].content
    assert question.question.question_id in data
    assert 'correct_choice_id' not in data and 'criteria' not in data
    assert 'not the final answer' in mock.calls[0].messages[0].content
    assert store.read(context) == before


def test_hint_rejects_answered_missing_foreign_and_removed_questions(gap):
    context, store, assessment = gap
    service, mock = teaching(store, [])
    with pytest.raises(ConversationError, match='already answered'):
        asyncio.run(service.hint(context, assessment.question_id))
    with pytest.raises(ConversationError, match='question'):
        asyncio.run(service.hint(context, 'missing'))
    with pytest.raises(SessionNotFoundError):
        asyncio.run(service.hint(context.model_copy(update={'learner_id': 'other'}), assessment.question_id))
    assessor = AssessmentService(store, MockLLM([MC]))
    question = asyncio.run(assessor.generate_multiple_choice(context, 'bubble-sort'))
    session = store.read(context)
    session.active_topic.roadmap.graph.concepts.pop()
    store._save(context, session)
    with pytest.raises(ConversationError, match='not in'):
        asyncio.run(service.hint(context, question.question.question_id))
    assert mock.calls == []


@pytest.mark.parametrize('method', ['hint', 'example'])
def test_hint_and_example_failure_preserve_state(gap, method):
    context, store, assessment = gap
    if method == 'hint':
        question = asyncio.run(AssessmentService(store, MockLLM([MC])).generate_multiple_choice(context, 'bubble-sort'))
        identifier = question.question.question_id
    else:
        identifier = assessment.assessment_id
    service, _ = teaching(store, [{'text': 'x' * 1001}])
    before = store.read(context)
    with pytest.raises(LLMError):
        asyncio.run(getattr(service, method)(context, identifier))
    assert store.read(context) == before


def add_selection(context, store, *, correct=False, concept_id='bubble-sort'):
    assessor = AssessmentService(store, MockLLM([MC]))
    question = asyncio.run(assessor.generate_multiple_choice(context, concept_id))
    return asyncio.run(assessor.evaluate(context, MultipleChoiceAnswer(question_id=question.question.question_id, selected_choice_id='a' if correct else 'b')))


def test_repeated_struggles_change_approach_and_success_resets(gap):
    context, store, assessment = gap
    service, mock = teaching(store, [{'text': 'A focused explanation.'}] * 4)
    asyncio.run(service.explain(context, assessment.assessment_id))
    second = add_selection(context, store)
    asyncio.run(service.explain(context, second.assessment_id))
    add_selection(context, store)
    fourth = add_selection(context, store)
    before = store.read(context)
    asyncio.run(service.example(context, fourth.assessment_id))
    assert store.read(context) == before
    add_selection(context, store, correct=True)
    new_gap = add_selection(context, store)
    asyncio.run(service.explain(context, new_gap.assessment_id))
    assert '"teaching_approach": "direct"' in mock.calls[0].messages[1].content
    assert 'smaller worked steps' in mock.calls[1].messages[0].content
    assert 'familiar analogy' in mock.calls[2].messages[0].content
    assert '"teaching_approach": "direct"' in mock.calls[3].messages[1].content


def test_uncertain_and_other_concept_evidence_do_not_count_as_struggle(gap):
    from athena_agent.teaching import teaching_approach
    context, store, _ = gap
    other = add_selection(context, store, concept_id='comparison')
    second = add_selection(context, store)
    session = store.read(context)
    session.active_topic.assessment_records[-1].assessment.outcome = 'uncertain'
    store._save(context, session)
    assert teaching_approach(store.read(context).active_topic, 'bubble-sort') == 'direct'
    session = store.read(context)
    session.active_topic.assessment_records[-1].assessment.outcome = 'partial'
    session.active_topic.assessment_records[-1].assessment.confidence = 0.4
    store._save(context, session)
    assert teaching_approach(store.read(context).active_topic, 'bubble-sort') == 'direct'


@pytest.mark.parametrize('format', ['text', 'diagram', 'animation', 'simulation'])
def test_format_recommendation_is_description_without_state_change(gap, format):
    context, store, _ = gap
    service, mock = teaching(store, [{'format': format, 'rationale': 'Shows how adjacent swaps move values.'}])
    before = store.read(context)
    recommendation = asyncio.run(service.recommend_format(context, 'bubble-sort'))
    assert recommendation.format == format and recommendation.concept_id == 'bubble-sort'
    assert 'specific pedagogical benefit' in mock.calls[0].messages[0].content
    assert 'Trace a complete sorting pass.' in mock.calls[0].messages[1].content
    assert store.read(context) == before


def test_format_recommendation_rejects_code_unknown_and_foreign_input(gap):
    context, store, _ = gap
    service, mock = teaching(store, [{'format': 'html', 'rationale': 'Render this', 'code': '<script/>'}])
    before = store.read(context)
    with pytest.raises(ConversationError, match='not in'):
        asyncio.run(service.recommend_format(context, 'missing'))
    with pytest.raises(SessionNotFoundError):
        asyncio.run(service.recommend_format(context.model_copy(update={'learner_id': 'other'}), 'bubble-sort'))
    assert mock.calls == []
    with pytest.raises(LLMError):
        asyncio.run(service.recommend_format(context, 'bubble-sort'))
    assert store.read(context) == before
