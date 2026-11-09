import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from athena_agent.context import ContextBudgetError
from athena_agent.conversation import ConversationError, ConversationTurn, SessionNotFoundError
from athena_agent.conversation_manager import ConversationManager
from athena_agent.learning import ConceptMastery
from athena_agent.llm import DependencyError, InvalidOutputError, LLMError, MockLLM
from athena_agent.planning import PlanningPolicy, PlanningService
from athena_agent.roadmap import RoadmapRevision
from .test_session_planning import planning_data, setup_planner


@pytest.fixture
def prepared(planning_data):
    context, store, _, planner = setup_planner(planning_data)
    asyncio.run(planner.plan(context))
    draft = store.read(context)
    draft.active_topic.learning_state.current_concept_id = 'bubble-sort'
    draft.active_topic.learning_state.phase = 'reinforce'
    draft.active_topic.learning_state.mastery = [
        ConceptMastery(concept_id='comparison', status='mastered', assessment_ids=['e1']),
        ConceptMastery(concept_id='bubble-sort', status='developing', assessment_ids=['e2']),
    ]
    store._save(context, draft)
    store.append_turn(context, ConversationTurn(user_text='Earlier question', assistant_text='Earlier reply'))
    return context, store


def revision_data(planning_data, *, goal='Bubble Sort'):
    return {
        'relation': 'same_topic', 'goal': goal,
        'scope': deepcopy(planning_data[0]), 'graph': deepcopy(planning_data[1]),
    }


def planner_for(store, responses, **kwargs):
    from athena_agent.reliable_llm import ReliableLLM, RetryPolicy
    mock = MockLLM(responses)
    return PlanningService(ReliableLLM(mock, policy=RetryPolicy(max_attempts=1)), store=store, **kwargs), mock


def test_revision_expands_graph_and_preserves_evidence(prepared, planning_data):
    context, store = prepared
    proposal = revision_data(planning_data)
    proposal['graph']['concepts'].append({
        'concept_id': 'complexity', 'title': 'Time complexity',
        'description': 'Analyse the number of comparisons.', 'prerequisite_ids': ['bubble-sort'],
    })
    objectives = deepcopy(planning_data[2])
    objectives['concepts'].append({'concept_id': 'complexity', 'objectives': ['Explain quadratic work.'], 'difficulty': 'advanced'})
    before = store.read(context)
    planner, mock = planner_for(store, [proposal, objectives])
    result = asyncio.run(planner.revise(context))
    after = store.read(context)
    assert len(result.graph.concepts) == 3
    assert after.active_topic.learning_state == before.active_topic.learning_state
    assert after.history == before.history
    assert after.active_topic.topic_id == before.active_topic.topic_id
    assert after.revision == before.revision + 1
    assert result.eligible_concept_ids(after.active_topic.learning_state) == ['bubble-sort']
    assert 'e1' in mock.calls[0].messages[1].content
    assert '"roadmap"' in mock.calls[0].messages[1].content
    result.graph.concepts[0].title = 'Changed'
    assert store.read(context).active_topic.roadmap.graph.concepts[0].title != 'Changed'


def test_goal_refinement_updates_goal_and_roadmap_together(prepared, planning_data):
    context, store = prepared
    before = store.read(context)
    planner, _ = planner_for(store, [revision_data(planning_data, goal='Explain Bubble Sort complexity'), planning_data[2]])
    result = asyncio.run(planner.revise(context, 'Focus on explaining the time complexity.'))
    after = store.read(context)
    assert after.active_topic.learning_state.goal == result.goal == 'Explain Bubble Sort complexity'
    assert after.active_topic.learning_state.mastery == before.active_topic.learning_state.mastery
    assert after.history == before.history


def test_unrequested_goal_change_is_rejected(prepared, planning_data):
    context, store = prepared
    before = store.read(context)
    planner, mock = planner_for(store, [revision_data(planning_data, goal='Another goal')])
    with pytest.raises(InvalidOutputError):
        asyncio.run(planner.revise(context))
    assert len(mock.calls) == 1
    assert store.read(context) == before


def test_unrelated_request_requires_topic_switch(prepared):
    context, store = prepared
    before = store.read(context)
    planner, mock = planner_for(store, [{'relation': 'unrelated'}])
    with pytest.raises(ConversationError, match='topic switch'):
        asyncio.run(planner.revise(context, 'Study Roman history instead.'))
    assert len(mock.calls) == 1
    assert store.read(context) == before


def test_removed_concept_keeps_historical_mastery_and_clears_current_pointer(prepared, planning_data):
    context, store = prepared
    before = store.read(context)
    proposal = revision_data(planning_data)
    proposal['graph']['concepts'].pop()
    objectives = deepcopy(planning_data[2])
    objectives['concepts'].pop()
    planner, _ = planner_for(store, [proposal, objectives])
    asyncio.run(planner.revise(context, 'Focus only on comparisons for now.'))
    after = store.read(context)
    assert after.active_topic.learning_state.mastery == before.active_topic.learning_state.mastery
    assert after.active_topic.learning_state.current_concept_id is None
    assert after.active_topic.learning_state.phase == before.active_topic.learning_state.phase
    assert after.history == before.history


@pytest.mark.parametrize('change', ['missing_prerequisite', 'cycle', 'repurposed_id', 'renamed_id', 'excess_expansion'])
def test_invalid_revisions_leave_existing_roadmap_unchanged(prepared, planning_data, change):
    context, store = prepared
    proposal = revision_data(planning_data)
    concepts = proposal['graph']['concepts']
    if change == 'missing_prerequisite':
        concepts.pop(0)
    elif change == 'cycle':
        concepts[0]['prerequisite_ids'] = ['bubble-sort']
    elif change == 'repurposed_id':
        concepts[0]['title'] = 'Unrelated identity'
    elif change == 'renamed_id':
        concepts[0]['concept_id'] = 'new-comparison'
        concepts[1]['prerequisite_ids'] = ['new-comparison']
    else:
        concepts.extend([
            {'concept_id': f'new-{index}', 'title': f'New {index}', 'description': 'New concept', 'prerequisite_ids': []}
            for index in range(2)
        ])
    planner, _ = planner_for(store, [proposal], policy=PlanningPolicy(initial_concept_limit=1))
    before = store.read(context)
    with pytest.raises(InvalidOutputError):
        asyncio.run(planner.revise(context))
    assert store.read(context) == before


def test_removed_historical_ids_cannot_be_repurposed(prepared, planning_data):
    context, store = prepared
    draft = store.read(context)
    draft.active_topic.learning_state.mastery.append(ConceptMastery(concept_id='historic', assessment_ids=['old']))
    store._save(context, draft)
    proposal = revision_data(planning_data)
    proposal['graph']['concepts'].append({'concept_id': 'historic', 'title': 'Different concept', 'description': 'New meaning', 'prerequisite_ids': []})
    planner, _ = planner_for(store, [proposal])
    before = store.read(context)
    with pytest.raises(InvalidOutputError):
        asyncio.run(planner.revise(context))
    assert store.read(context) == before


def test_prerequisite_correction_is_allowed(prepared, planning_data):
    context, store = prepared
    proposal = revision_data(planning_data)
    proposal['graph']['concepts'][1]['prerequisite_ids'] = []
    planner, _ = planner_for(store, [proposal, planning_data[2]])
    revised = asyncio.run(planner.revise(context, 'Correct the prerequisite assumptions.'))
    assert revised.graph.concepts[1].prerequisite_ids == []


@pytest.mark.parametrize('stage', ['proposal', 'enrichment'])
def test_provider_failure_rolls_back_revision(prepared, planning_data, stage):
    context, store = prepared
    responses = [DependencyError('Unavailable')] if stage == 'proposal' else [revision_data(planning_data), DependencyError('Unavailable')]
    planner, _ = planner_for(store, responses)
    before = store.read(context)
    with pytest.raises(LLMError):
        asyncio.run(planner.revise(context))
    assert store.read(context) == before


def test_cancelled_revision_leaves_state_unchanged(prepared):
    context, store = prepared
    provider = AsyncMock()
    provider.generate.side_effect = asyncio.CancelledError()
    before = store.read(context)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(PlanningService(provider, store=store).revise(context))
    assert store.read(context) == before


def test_stale_revision_does_not_erase_newer_focus(prepared, planning_data):
    context, store = prepared
    responses = [revision_data(planning_data), planning_data[2]]

    class Provider:
        async def generate(self, messages, model):
            if len(responses) == 1:
                store.update_focus(context, 'Concurrent update')
            return model.model_validate(responses.pop(0))

    old_roadmap = store.read(context).active_topic.roadmap
    with pytest.raises(ConversationError, match='session changed'):
        asyncio.run(PlanningService(Provider(), store=store).revise(context))
    assert store.read(context).active_topic.roadmap == old_roadmap
    assert store.read(context).active_topic.discussion_focus == 'Concurrent update'


def test_missing_plan_cross_learner_and_blank_request_do_not_call_model():
    context, store, _, _ = setup_planner([])
    planner, mock = planner_for(store, [])
    with pytest.raises(ConversationError, match='Create a roadmap'):
        asyncio.run(planner.revise(context))
    with pytest.raises(SessionNotFoundError):
        asyncio.run(planner.revise(context.model_copy(update={'learner_id': 'other'})))
    with pytest.raises(ValidationError):
        asyncio.run(planner.revise(context, ' '))
    assert mock.calls == []


def test_large_existing_graph_is_budgeted_before_revision_call(prepared):
    context, store = prepared
    from athena_agent.context import ContextBudget, ContextBuilder
    planner, mock = planner_for(store, [], context_builder=ContextBuilder(ContextBudget(context_window=3000)))
    before = store.read(context)
    with pytest.raises(ContextBudgetError):
        asyncio.run(planner.revise(context))
    assert mock.calls == []
    assert store.read(context) == before


def test_topic_switch_archives_roadmap_and_new_topic_has_none(prepared):
    context, store = prepared
    old = store.read(context).active_topic.roadmap
    manager = ConversationManager(store, MockLLM([
        {'intent': 'topic_change', 'new_goal': 'Graph theory'}, {'text': 'Graph introduction'},
    ]))
    asyncio.run(manager.send(context, 'Switch to graph theory.'))
    session = store.read(context)
    assert session.active_topic.roadmap is None
    assert session.archived_topics[-1].roadmap == old


@pytest.mark.parametrize('values', [
    {'relation': 'same_topic'},
    {'relation': 'unrelated', 'goal': 'Graphs'},
])
def test_revision_proposal_requires_consistent_fields(values):
    with pytest.raises(ValidationError):
        RoadmapRevision(**values)


def test_broad_foundations_expand_from_prerequisite_evidence():
    import json
    from pathlib import Path
    data = json.loads((Path(__file__).parent / 'fixtures' / 'planning_machine_learning.json').read_text())
    context, store, _, _ = setup_planner([])
    # Start a separate broad-topic session through the ordinary store boundary.
    broad = context.model_copy(update={'session_id': 'machine-learning'})
    store.create(broad)
    store.initialize_goal(broad, 'Learn Machine Learning')
    planner, _ = planner_for(store, [data['scope'], data['graph'], data['objectives']])
    roadmap = asyncio.run(planner.plan(broad))
    assert roadmap.graph.partial_coverage
    assert roadmap.eligible_concept_ids(store.read(broad).active_topic.learning_state) == ['linear-algebra', 'probability']
    draft = store.read(broad)
    draft.active_topic.learning_state.mastery = [
        ConceptMastery(concept_id='linear-algebra', status='mastered', assessment_ids=['math-e1']),
        ConceptMastery(concept_id='probability', status='developing', assessment_ids=['math-e2']),
    ]
    store._save(broad, draft)
    proposal = {
        'relation': 'same_topic', 'goal': 'Learn Machine Learning',
        'scope': data['scope'], 'graph': data['graph'],
    }
    proposal['graph']['concepts'].append({
        'concept_id': 'evaluation', 'title': 'Model evaluation',
        'description': 'Interpret held-out prediction errors.', 'prerequisite_ids': ['linear-regression'],
    })
    data['objectives']['concepts'].append({
        'concept_id': 'evaluation', 'objectives': ['Explain why to hold out test data.'], 'difficulty': 'intermediate',
    })
    planner, mock = planner_for(store, [proposal, data['objectives']])
    updated = asyncio.run(planner.revise(broad))
    assert updated.graph.partial_coverage
    assert updated.eligible_concept_ids(store.read(broad).active_topic.learning_state) == ['probability']
    assert 'math-e2' in mock.calls[0].messages[1].content
    assert store.read(context).active_topic.roadmap is None


def test_expansion_limit_counts_new_ids_even_when_others_are_removed(prepared, planning_data):
    context, store = prepared
    proposal = revision_data(planning_data)
    proposal['graph']['concepts'].pop()  # Total size remains within old size + 1.
    proposal['graph']['concepts'].extend([
        {'concept_id': f'new-{index}', 'title': f'New {index}', 'description': 'New', 'prerequisite_ids': []}
        for index in range(2)
    ])
    planner, _ = planner_for(store, [proposal], policy=PlanningPolicy(initial_concept_limit=1))
    before = store.read(context)
    with pytest.raises(InvalidOutputError):
        asyncio.run(planner.revise(context))
    assert store.read(context) == before


def test_broad_revision_cannot_claim_complete_coverage(planning_data):
    proposal = revision_data(planning_data)
    proposal['scope'] = {'scope': 'broad', 'rationale': 'A wider field'}
    with pytest.raises(ValidationError, match='partial coverage'):
        RoadmapRevision.model_validate(proposal)
