import asyncio

import pytest
from pydantic import ValidationError

from athena_agent.assessment import AssessmentService
from athena_agent.learning import TeachingContent
from athena_agent.llm import MockLLM
from .test_teaching import gap, teaching
from .test_assessment import assessed_topic
from .test_session_planning import planning_data


def test_structured_teaching_keeps_text_alternative_and_bounds(gap):
    context, store, assessment = gap
    teacher, _ = teaching(store, [{'text': 'Compare neighbours. For [2, 1], swap them.', 'content': {'summary': 'Compare neighbours.', 'steps': ['Check whether the pair is out of order.', 'Swap if needed.'], 'worked_example': '[2, 1] becomes [1, 2].'}}])
    activity = asyncio.run(teacher.explain(context, assessment.assessment_id))
    assert activity.content.steps == ['Check whether the pair is out of order.', 'Swap if needed.']
    assert activity.text and activity.content.worked_example
    with pytest.raises(ValidationError):
        TeachingContent(summary='word ' * 121)
    with pytest.raises(ValidationError):
        TeachingContent(summary='Small unit', steps=['one'] * 5)


def test_text_only_generation_produces_compatible_structured_summary(gap):
    context, store, assessment = gap
    teacher, _ = teaching(store, [{'text': 'Compare adjacent values.'}])
    activity = asyncio.run(teacher.explain(context, assessment.assessment_id))
    assert activity.content.summary == activity.text


def test_feedback_content_is_derived_from_assessment_without_private_criteria(gap):
    context, store, assessment = gap
    before = store.read(context)
    activity = AssessmentService(store, MockLLM([])).feedback_activity(context, assessment.assessment_id)
    assert activity.content.outcome == assessment.outcome
    assert activity.content.message == activity.text == assessment.feedback
    assert 'correct_choice_id' not in activity.model_dump_json()
    assert store.read(context) == before


def test_text_only_explanation_at_character_boundary_keeps_valid_fallback(gap):
    context, store, assessment = gap
    text = 'x' * 1000
    teacher, _ = teaching(store, [{'text': text}])
    activity = asyncio.run(teacher.explain(context, assessment.assessment_id))
    assert activity.text == activity.content.summary == text
