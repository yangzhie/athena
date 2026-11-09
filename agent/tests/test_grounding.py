import asyncio

import pytest

from athena_agent.assessment import AssessmentService
from athena_agent.llm import LLMError, MockLLM
from athena_agent.planning import PlanningService
from athena_agent.teaching import TeachingService
from .test_assessment import assessed_topic, MC, service
from .test_session_planning import planning_data
from .test_teaching import gap, teaching
from .test_knowledge import material


def select_materials(context, store):
    session = store.read(context)
    session.active_topic.knowledge = material()
    store._save(context, session)
    item = material().items[0]
    return {'supported': True, 'evidence': [{'source_index': 0, 'quote': item.text}]}


def test_teaching_requires_exact_source_support(gap):
    context, store, assessment = gap
    support = select_materials(context, store)
    teacher, mock = teaching(store, [{'text': 'Compare adjacent values.'}, support])
    activity = asyncio.run(teacher.explain(context, assessment.assessment_id))
    assert activity.concept_id == assessment.concept_id and len(mock.calls) == 2
    assert 'selected_materials' in mock.calls[0].messages[1].content
    assert 'generated_content' in mock.calls[1].messages[1].content
    before = store.read(context)
    for check in [{'supported': False, 'evidence': []}, {'supported': True, 'evidence': [{'source_index': 0, 'quote': 'Invented quote'}]}]:
        teacher, _ = teaching(store, [{'text': 'An unsupported claim.'}, check])
        with pytest.raises(LLMError):
            asyncio.run(teacher.explain(context, assessment.assessment_id))
        assert store.read(context) == before


def test_assessment_generation_is_grounded_without_exposing_criteria(assessed_topic):
    context, store = assessed_topic
    support = select_materials(context, store)
    assessor, mock = service(store, [MC, support])
    activity = asyncio.run(assessor.generate_multiple_choice(context, 'bubble-sort'))
    assert 'criteria' not in activity.model_dump_json()
    assert 'correct_choice_id' in mock.calls[1].messages[1].content
    assert len(mock.calls) == 2


def test_planning_selected_sources_reach_each_planning_stage(planning_data):
    from .test_session_planning import setup_planner
    context, store, _, _ = setup_planner([])
    support = select_materials(context, store)
    mock = MockLLM([planning_data[0], support, planning_data[1], support, planning_data[2], support])
    roadmap = asyncio.run(PlanningService(mock, store=store).plan(context))
    assert roadmap.goal == 'Bubble Sort' and len(mock.calls) == 6
    assert all('selected_materials' in call.messages[1].content for call in mock.calls)
