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


def test_client_capabilities_gate_recommendations_and_default_to_text(gap):
    from athena_agent.activities import ClientCapabilities
    from athena_agent.content import ContentService
    context, store, _ = gap
    mock = MockLLM([{'format': 'animation', 'rationale': 'Shows adjacent swaps over time.'}, {'format': 'simulation', 'rationale': 'Explore swaps.'}])
    service = ContentService(store, mock)
    assert asyncio.run(service.choose(context, 'bubble-sort')).format == 'text'
    assert mock.calls == []
    asyncio.run(service.set_capabilities(context, ClientCapabilities(formats=['animation'])))
    assert asyncio.run(service.choose(context, 'bubble-sort')).format == 'animation'
    assert asyncio.run(service.choose(context, 'bubble-sort')).format == 'text'
    before = store.read(context)
    asyncio.run(service.set_capabilities(context, ClientCapabilities(formats=['animation'])))
    assert store.read(context) == before
    with pytest.raises(ValidationError):
        ClientCapabilities(formats=['html'])


def test_generate_validated_diagram_without_executing_ui(gap):
    from athena_agent.activities import ClientCapabilities
    from athena_agent.content import ContentService
    context, store, _ = gap
    mock = MockLLM([{'format': 'diagram', 'rationale': 'Shows adjacent comparisons.'}, {'text': 'Compare two neighbouring items.', 'parameters': {'kind': 'diagram', 'nodes': [{'node_id': 'a', 'label': 'Left'}, {'node_id': 'b', 'label': 'Right'}], 'edges': [{'from_id': 'a', 'to_id': 'b', 'label': 'Compare'}]}}])
    service = ContentService(store, mock)
    asyncio.run(service.set_capabilities(context, ClientCapabilities(formats=['diagram'])))
    before = store.read(context)
    activity = asyncio.run(service.generate(context, 'bubble-sort'))
    assert activity.kind == 'rich' and activity.parameters.kind == 'diagram'
    assert activity.text and store.read(context) == before


@pytest.mark.parametrize('model,data', [
    ('DiagramParameters', {'nodes': [{'node_id': 'a', 'label': 'A'}], 'edges': [{'from_id': 'a', 'to_id': 'missing'}]}),
    ('AnimationParameters', {'frames': [{'label': 'Step', 'values': [1.0], 'highlight_indices': [1]}]}),
    ('SimulationParameters', {'variables': [{'name': 'x', 'minimum': 2.0, 'maximum': 1.0, 'initial': 1.0, 'step': 0.1}], 'relationship': 'More x means more y', 'observation_prompt': 'What changes?'}),
])
def test_invalid_rich_parameters_reject_inconsistent_references_and_ranges(model, data):
    from athena_agent import activities
    with pytest.raises(ValidationError):
        getattr(activities, model).model_validate(data)


@pytest.mark.parametrize('format,parameters', [
    ('animation', {'kind': 'animation', 'frames': [{'label': 'Compare', 'values': [2.0, 1.0], 'highlight_indices': [0, 1]}, {'label': 'Swap', 'values': [1.0, 2.0]}]}),
    ('simulation', {'kind': 'simulation', 'variables': [{'name': 'size', 'minimum': 1.0, 'maximum': 10.0, 'initial': 3.0, 'step': 1.0}], 'relationship': 'Larger inputs require more comparisons.', 'observation_prompt': 'How does increasing size affect comparisons?'}),
])
def test_generate_supported_animation_and_simulation(gap, format, parameters):
    from athena_agent.activities import ClientCapabilities
    from athena_agent.content import ContentService
    context, store, _ = gap
    mock = MockLLM([{'format': format, 'rationale': 'Shows the process.'}, {'text': 'Observe adjacent comparisons.', 'parameters': parameters}])
    service = ContentService(store, mock)
    asyncio.run(service.set_capabilities(context, ClientCapabilities(formats=[format])))
    activity = asyncio.run(service.generate(context, 'bubble-sort'))
    assert activity.parameters.kind == format and activity.text


def test_rich_content_attaches_verified_video_times_and_text_excerpt(gap):
    from athena_agent.activities import ClientCapabilities
    from athena_agent.content import ContentService
    from .test_grounding import select_materials
    from .test_knowledge import material
    context, store, _ = gap
    select_materials(context, store)
    video = material().items[1]
    support = {'supported': True, 'evidence': [{'source_index': 1, 'quote': video.transcript}]}
    mock = MockLLM([{'format': 'diagram', 'rationale': 'Shows comparison.'}, support, {'text': 'Compare adjacent values.', 'parameters': {'kind': 'diagram', 'nodes': [{'node_id': 'a', 'label': 'Compare'}]}}, support])
    service = ContentService(store, mock)
    asyncio.run(service.set_capabilities(context, ClientCapabilities(formats=['diagram'])))
    activity = asyncio.run(service.generate(context, 'bubble-sort'))
    attachment = activity.media[0]
    assert attachment.reference.start_seconds == video.start_seconds
    assert attachment.reference.end_seconds == video.end_seconds
    assert attachment.text_alternative == video.transcript
    assert attachment.reference in activity.sources
    altered = activity.model_dump()
    altered['media'][0]['reference']['source_uri'] = 'invented://wrong'
    with pytest.raises(ValidationError):
        type(activity).model_validate(altered)
