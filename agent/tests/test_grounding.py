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
    assert roadmap == store.read(context).active_topic.roadmap
    assert len(roadmap.sources) == 1
    assert all('selected_materials' in call.messages[1].content for call in mock.calls)


def test_returned_document_and_video_citations_copy_supplied_metadata(gap):
    context, store, assessment = gap
    support = select_materials(context, store)
    video = material().items[1]
    support['evidence'].append({'source_index': 1, 'quote': video.transcript})
    teacher, _ = teaching(store, [{'text': 'Compare adjacent values.'}, support])
    activity = asyncio.run(teacher.explain(context, assessment.assessment_id))
    document_ref, video_ref = activity.sources
    assert document_ref.passage_id == material().items[0].passage_id
    assert document_ref.page == material().items[0].page
    assert video_ref.start_seconds == video.start_seconds and video_ref.end_seconds == video.end_seconds
    assert video_ref.source_uri == video.source_uri and video_ref.quote in video.transcript
    assert '_source_references' not in activity.model_dump_json()


def test_question_citations_survive_saved_record_and_grading(assessed_topic):
    from athena_agent.learning import MultipleChoiceAnswer
    context, store = assessed_topic
    support = select_materials(context, store)
    assessor, _ = service(store, [MC, support])
    question = asyncio.run(assessor.generate_multiple_choice(context, 'bubble-sort'))
    record = store.read(context).active_topic.question_records[-1]
    assert question.sources == record.sources and len(question.sources) == 1
    grade = asyncio.run(assessor.evaluate(context, MultipleChoiceAnswer(question_id=question.question.question_id, selected_choice_id='a')))
    assert grade.sources == question.sources
