import asyncio
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from athena_agent.context import ContextBudget, ContextBudgetError, ContextBuilder
from athena_agent.llm import InvalidOutputError
from athena_agent.planning import PlanningPolicy
from athena_agent.roadmap import ConceptGraph, TopicScope
from .test_planning import service


@pytest.fixture
def graph_data():
    return json.loads((Path(__file__).parent / 'fixtures' / 'planning_graph.json').read_text())


def test_identify_graph_preserves_prerequisites_and_uses_measured_inputs(graph_data):
    planner, mock = service([graph_data])
    scope = TopicScope(scope='narrow', rationale='One technique')
    graph = asyncio.run(planner.identify_graph('Bubble Sort', scope))
    assert graph.concepts[1].prerequisite_ids == ['comparison']
    assert graph.model_dump() == graph_data
    assert '"planning_inputs"' in mock.calls[0].messages[1].content
    assert '"scope": "narrow"' in mock.calls[0].messages[1].content
    assert 'maxItems' in json.dumps(mock.calls[0].response_model.model_json_schema())
    assert ConceptGraph.model_validate_json(graph.model_dump_json()) == graph


@pytest.mark.parametrize('change', ['empty', 'duplicate', 'missing_reference', 'duplicate_prerequisite'])
def test_invalid_graphs(graph_data, change):
    if change == 'empty':
        graph_data['concepts'] = []
    elif change == 'duplicate':
        graph_data['concepts'][1]['concept_id'] = 'comparison'
    elif change == 'missing_reference':
        graph_data['concepts'][1]['prerequisite_ids'] = ['missing']
    else:
        graph_data['concepts'][1]['prerequisite_ids'] = ['comparison', 'comparison']
    with pytest.raises(ValidationError):
        ConceptGraph.model_validate(graph_data)


def test_initial_generation_limit_is_enforced(graph_data):
    planner, _ = service([graph_data], policy=PlanningPolicy(initial_concept_limit=1))
    with pytest.raises(InvalidOutputError):
        asyncio.run(planner.identify_graph('Bubble Sort', TopicScope(scope='narrow', rationale='Technique')))


def test_broad_subject_requires_partial_foundation(graph_data):
    planner, _ = service([graph_data])
    scope = TopicScope(scope='broad', rationale='Many concept families')
    with pytest.raises(InvalidOutputError):
        asyncio.run(planner.identify_graph('Machine Learning', scope))
    graph_data['partial_coverage'] = True
    planner, _ = service([graph_data])
    assert asyncio.run(planner.identify_graph('Machine Learning', scope)).partial_coverage


def test_large_scope_input_is_budgeted_before_model_call():
    planner, mock = service([], context_builder=ContextBuilder(ContextBudget(context_window=6000)))
    with pytest.raises(ContextBudgetError):
        asyncio.run(planner.identify_graph('Machine Learning', TopicScope(scope='broad', rationale='x' * 10000)))
    assert mock.calls == []


def test_invalid_generation_policy():
    with pytest.raises(ValidationError):
        PlanningPolicy(initial_concept_limit=0)


@pytest.fixture
def objectives_data():
    return json.loads((Path(__file__).parent / 'fixtures' / 'planning_objectives.json').read_text())


def test_enrichment_preserves_graph_and_uses_evidence(graph_data, objectives_data):
    from athena_agent.learning import ConceptMastery, LearningState
    from athena_agent.roadmap import EnrichedGraph

    graph = ConceptGraph.model_validate(graph_data)
    state = LearningState(goal='Bubble Sort', mastery=[
        ConceptMastery(concept_id='comparison', status='developing', assessment_ids=['e1']),
    ])
    before = state.model_dump()
    planner, mock = service([objectives_data])
    result = asyncio.run(planner.enrich_graph(graph, goal='Bubble Sort', learner_state=state))
    assert result.concepts[1].difficulty == 'intermediate'
    assert len(result.concepts[1].objectives) == 2
    for original, enriched in zip(graph.concepts, result.concepts):
        assert enriched.model_dump(exclude={'objectives', 'difficulty'}) == original.model_dump()
    assert state.model_dump() == before
    assert 'e1' in mock.calls[0].messages[1].content
    assert EnrichedGraph.model_validate_json(result.model_dump_json()) == result
    json.dumps(EnrichedGraph.model_json_schema())


@pytest.mark.parametrize('change', ['missing', 'added', 'duplicate', 'changed_edges', 'blank_objective', 'no_objectives', 'bad_difficulty'])
def test_invalid_enrichment_is_rejected(graph_data, objectives_data, change):
    if change == 'missing':
        objectives_data['concepts'].pop()
    elif change == 'added':
        objectives_data['concepts'].append({'concept_id': 'unrequested', 'objectives': ['Explain'], 'difficulty': 'beginner'})
    elif change == 'duplicate':
        objectives_data['concepts'][1]['concept_id'] = 'comparison'
    elif change == 'changed_edges':
        objectives_data['concepts'][0]['prerequisite_ids'] = ['bubble-sort']
    elif change == 'blank_objective':
        objectives_data['concepts'][0]['objectives'] = [' ']
    elif change == 'no_objectives':
        objectives_data['concepts'][0]['objectives'] = []
    else:
        objectives_data['concepts'][0]['difficulty'] = 'expert'
    planner, _ = service([objectives_data])
    with pytest.raises(InvalidOutputError):
        asyncio.run(planner.enrich_graph(ConceptGraph.model_validate(graph_data), goal='Bubble Sort'))


def test_enrichment_rejects_unrelated_learning_state_before_call(graph_data):
    from athena_agent.conversation import ConversationError
    from athena_agent.learning import LearningState
    planner, mock = service([])
    with pytest.raises(ConversationError, match='requested goal'):
        asyncio.run(planner.enrich_graph(
            ConceptGraph.model_validate(graph_data), goal='Bubble Sort', learner_state=LearningState(goal='Graphs'),
        ))
    assert mock.calls == []
