import asyncio
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from athena_agent.context import ContextBudget, ContextBudgetError, ContextBuilder
from athena_agent.conversation import ConversationError, ConversationTurn, InMemoryConversationStore, SessionNotFoundError
from athena_agent.contracts import RequestContext
from athena_agent.learning import ConceptMastery, LearningState
from athena_agent.llm import DependencyError, LLMError, MockLLM
from athena_agent.planning import PlanningService
from athena_agent.reliable_llm import ReliableLLM, RetryPolicy
from athena_agent.roadmap import ConceptGraph, Roadmap


@pytest.fixture
def planning_data():
    fixtures = Path(__file__).parent / 'fixtures'
    return [
        {'scope': 'narrow', 'rationale': 'One technique'},
        json.loads((fixtures / 'planning_graph.json').read_text()),
        json.loads((fixtures / 'planning_objectives.json').read_text()),
    ]


def setup_planner(responses, **kwargs):
    context = RequestContext(request_id='r1', learner_id='l1', session_id='s1')
    store = InMemoryConversationStore()
    store.create(context)
    store.initialize_goal(context, 'Bubble Sort')
    mock = MockLLM(responses)
    planner = PlanningService(ReliableLLM(mock, policy=RetryPolicy(max_attempts=1)), store=store, **kwargs)
    return context, store, mock, planner


def test_plan_attaches_atomically_and_returns_independent_snapshot(planning_data):
    context, store, mock, planner = setup_planner(planning_data)
    store.append_turn(context, ConversationTurn(user_text='Start', assistant_text='Ready'))
    before = store.read(context)
    roadmap = asyncio.run(planner.plan(context))
    after = store.read(context)
    assert roadmap == after.active_topic.roadmap
    assert after.active_topic.learning_state == before.active_topic.learning_state
    assert after.history == before.history
    assert after.revision == before.revision + 1
    assert len(mock.calls) == 3
    roadmap.graph.concepts[0].title = 'Changed'
    assert store.read(context).active_topic.roadmap.graph.concepts[0].title != 'Changed'
    assert Roadmap.model_validate_json(after.active_topic.roadmap.model_dump_json()) == after.active_topic.roadmap


def test_eligible_concepts_are_prerequisite_driven(planning_data):
    context, store, _, planner = setup_planner(planning_data)
    roadmap = asyncio.run(planner.plan(context))
    state = store.read(context).active_topic.learning_state
    assert roadmap.eligible_concept_ids(state) == ['comparison']
    state.mastery = [ConceptMastery(concept_id='comparison', status='mastered', assessment_ids=['e1'])]
    assert roadmap.eligible_concept_ids(state) == ['bubble-sort']
    state.mastery.append(ConceptMastery(concept_id='bubble-sort', status='mastered', assessment_ids=['e2']))
    assert roadmap.eligible_concept_ids(state) == []
    with pytest.raises(ValueError, match='match'):
        roadmap.eligible_concept_ids(LearningState(goal='Graphs'))


@pytest.mark.parametrize('failure_at', [0, 1, 2])
def test_planning_failure_rolls_back_every_stage(planning_data, failure_at):
    responses = planning_data[:failure_at] + [DependencyError('Unavailable')]
    context, store, _, planner = setup_planner(responses)
    before = store.read(context)
    with pytest.raises(LLMError):
        asyncio.run(planner.plan(context))
    assert store.read(context) == before


def test_cancellation_does_not_save_partial_plan():
    context, store, _, _ = setup_planner([])
    before = store.read(context)

    class Provider:
        async def generate(self, messages, model):
            raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(PlanningService(Provider(), store=store).plan(context))
    assert store.read(context) == before


def test_existing_plan_and_cross_learner_access_fail_before_model(planning_data):
    context, store, mock, planner = setup_planner(planning_data)
    asyncio.run(planner.plan(context))
    with pytest.raises(ConversationError, match='revise'):
        asyncio.run(planner.plan(context))
    with pytest.raises(SessionNotFoundError):
        asyncio.run(planner.plan(context.model_copy(update={'learner_id': 'other'})))
    assert len(mock.calls) == 3


def test_missing_goal_and_missing_store_fail_before_model():
    context, store, mock, planner = setup_planner([])
    other = context.model_copy(update={'session_id': 'other'})
    store.create(other)
    with pytest.raises(ConversationError, match='Initialize'):
        asyncio.run(planner.plan(other))
    with pytest.raises(ConversationError, match='store'):
        asyncio.run(PlanningService(mock).plan(context))
    assert mock.calls == []


def test_context_overflow_does_not_change_topic():
    context, store, mock, planner = setup_planner([], context_builder=ContextBuilder(ContextBudget(context_window=3000)))
    draft = store.read(context)
    draft.active_topic.learning_state.goal = 'x' * 10000
    store._save(context, draft)
    before = store.read(context)
    with pytest.raises(ContextBudgetError):
        asyncio.run(planner.plan(context))
    assert store.read(context) == before
    assert mock.calls == []


@pytest.mark.parametrize('cycle', ['self', 'two_nodes'])
def test_cycles_rejected_at_graph_boundary(planning_data, cycle):
    data = planning_data[1]
    if cycle == 'self':
        data['concepts'][0]['prerequisite_ids'] = ['comparison']
    else:
        data['concepts'][0]['prerequisite_ids'] = ['bubble-sort']
    with pytest.raises(ValidationError):
        ConceptGraph.model_validate(data)


def test_stale_plan_does_not_overwrite_newer_state(planning_data):
    context, store, _, _ = setup_planner([])

    class Provider:
        async def generate(self, messages, model):
            index = len(calls)
            calls.append(model)
            if index == 2:
                store.update_focus(context, 'Newer change')
            return model.model_validate(planning_data[index])

    calls = []
    with pytest.raises(ConversationError, match='session changed'):
        asyncio.run(PlanningService(Provider(), store=store).plan(context))
    assert store.read(context).active_topic.roadmap is None
    assert store.read(context).active_topic.discussion_focus == 'Newer change'


def test_objective_schema_cannot_invent_concept_ids(planning_data):
    from athena_agent.roadmap import ConceptGraph
    from athena_agent.planning import PlanningService
    from athena_agent.llm import MockLLM
    from pydantic import ValidationError
    import pytest
    graph = ConceptGraph.model_validate(planning_data[1])
    mock = MockLLM([planning_data[2]])
    asyncio.run(PlanningService(mock).enrich_graph(graph, goal='Bubble Sort'))
    schema = mock.calls[-1].response_model
    wrong = dict(planning_data[2])
    wrong['concepts'] = [{**wrong['concepts'][0], 'concept_id': 'invented-other-id'}]
    with pytest.raises(ValidationError):
        schema.model_validate(wrong)
