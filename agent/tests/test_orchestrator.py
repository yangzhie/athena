import asyncio
from unittest.mock import AsyncMock

import pytest

from athena_agent.conversation import ConversationError, InMemoryConversationStore, SessionNotFoundError
from athena_agent.contracts import RequestContext
from athena_agent.llm import DependencyError, MockLLM, LLMError
from athena_agent.orchestrator import LearningOrchestrator
from athena_agent.reliable_llm import ReliableLLM, RetryPolicy
from .test_assessment import MC
from .test_session_planning import planning_data


def setup(responses):
    store = InMemoryConversationStore()
    context = RequestContext(request_id='r', learner_id='learner', session_id='session')
    mock = MockLLM(responses)
    orchestrator = LearningOrchestrator(store, ReliableLLM(mock, policy=RetryPolicy(max_attempts=1)))
    return context, store, mock, orchestrator


@pytest.mark.parametrize('scope', ['narrow', 'broad'])
@pytest.mark.parametrize('difficulty', ['beginner', 'advanced'])
def test_start_proactively_diagnoses_without_assuming_mastery(planning_data, scope, difficulty):
    planning_data[0]['scope'] = scope
    planning_data[1]['partial_coverage'] = scope == 'broad'
    context, store, mock, orchestrator = setup([*planning_data, MC])
    activity = asyncio.run(orchestrator.start(context, 'Bubble Sort', difficulty=difficulty))
    topic = store.read(context).active_topic
    assert activity.question.concept_id == 'comparison'  # prerequisite first
    assert activity.question.difficulty == difficulty
    assert topic.current_activity == activity
    assert topic.learning_state.phase == 'diagnose' and topic.learning_state.mastery == []
    assert topic.roadmap.scope.scope == scope
    assert len(mock.calls) == 4
    assert 'criteria' not in activity.model_dump_json()
    with pytest.raises(ConversationError, match='already exists'):
        asyncio.run(orchestrator.start(context, 'Other goal'))
    assert len(mock.calls) == 4


@pytest.mark.parametrize('failure_at', range(4))
def test_failed_start_can_retry_without_partial_session(planning_data, failure_at):
    context, store, _, orchestrator = setup([*planning_data[:failure_at], DependencyError('Unavailable')])
    with pytest.raises(LLMError):
        asyncio.run(orchestrator.start(context, 'Bubble Sort'))
    with pytest.raises(SessionNotFoundError):
        store.read(context)
    retry = LearningOrchestrator(store, MockLLM([*planning_data, MC]))
    assert asyncio.run(retry.start(context, 'Bubble Sort')).kind == 'question'


def test_cancelled_start_does_not_publish_session():
    context, store, _, _ = setup([])
    provider = AsyncMock()
    provider.generate.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(LearningOrchestrator(store, provider).start(context, 'Bubble Sort'))
    with pytest.raises(SessionNotFoundError):
        store.read(context)


def test_concurrent_starts_publish_one_session(planning_data):
    context, store, mock, orchestrator = setup([*planning_data, MC])
    async def run():
        return await asyncio.gather(orchestrator.start(context, 'Bubble Sort'), orchestrator.start(context, 'Bubble Sort'), return_exceptions=True)
    results = asyncio.run(run())
    assert sum(isinstance(result, ConversationError) for result in results) == 1
    assert len(store.read(context).active_topic.question_records) == 1
    assert len(mock.calls) == 4


def test_start_evaluation_scenarios_are_repeatable():
    import json
    from pathlib import Path
    from athena_agent.evaluation import evaluate_fixture
    fixture = json.loads((Path(__file__).parent / 'fixtures/session_start.json').read_text())
    first = asyncio.run(evaluate_fixture(fixture))
    assert first['passed'] and len(first['results']) == 4
    assert first == asyncio.run(evaluate_fixture(fixture))


OPEN = {'prompt': 'Apply adjacent comparisons to [5, 2] and explain.', 'expected_reasoning': 'Compare 5 and 2 and swap neighbours.'}


def started(planning_data, responses):
    context, store, mock, orchestrator = setup([*planning_data, MC, *responses])
    question = asyncio.run(orchestrator.start(context, 'Bubble Sort'))
    return context, store, mock, orchestrator, question


def test_wrong_diagnostic_teaches_then_reinforces_atomically(planning_data):
    from athena_agent.learning import MultipleChoiceAnswer
    context, store, mock, orchestrator, question = started(planning_data, [
        {'misconceptions': [], 'prerequisite_gaps': []}, {'text': 'Compare neighbours rather than random pairs.'}, OPEN,
    ])
    answer = MultipleChoiceAnswer(question_id=question.question.question_id, selected_choice_id='b')
    teaching = asyncio.run(orchestrator.answer(context, answer))
    topic = store.read(context).active_topic
    assert teaching.kind == 'explanation' and topic.learning_state.phase == 'teach'
    assert topic.learning_state.mastery[0].status == 'developing'
    before = store.read(context)
    assert asyncio.run(orchestrator.answer(context, answer)) == teaching
    assert store.read(context) == before
    reinforcement = asyncio.run(orchestrator.continue_learning(context, teaching.activity_id))
    assert reinforcement.kind == 'question'
    assert store.read(context).active_topic.learning_state.phase == 'reinforce'
    assert len(store.read(context).history) == 1


def test_correct_selection_requires_reasoning_before_progress(planning_data):
    from athena_agent.learning import MultipleChoiceAnswer, TextAnswer
    context, store, _, orchestrator, question = started(planning_data, [OPEN, {
        'outcome': 'correct', 'feedback': 'Good reasoning.', 'confidence': 0.95, 'evidence_quotes': ['swap neighbours'],
    }, MC])
    followup = asyncio.run(orchestrator.answer(context, MultipleChoiceAnswer(question_id=question.question.question_id, selected_choice_id='a')))
    assert store.read(context).active_topic.learning_state.mastery[0].status == 'developing'
    next_question = asyncio.run(orchestrator.answer(context, TextAnswer(question_id=followup.question.question_id, text='Compare 5 and 2 and swap neighbours.')))
    assert next_question.question.concept_id == 'bubble-sort'
    assert store.read(context).active_topic.learning_state.mastery[0].status == 'mastered'
    assert len(store.read(context).history) == 2


def test_downstream_failure_rolls_back_answer_and_mastery(planning_data):
    from athena_agent.learning import MultipleChoiceAnswer
    context, store, _, orchestrator, question = started(planning_data, [DependencyError('Unavailable')])
    before = store.read(context)
    with pytest.raises(LLMError):
        asyncio.run(orchestrator.answer(context, MultipleChoiceAnswer(question_id=question.question.question_id, selected_choice_id='a')))
    assert store.read(context) == before


def test_answer_cancellation_and_wrong_question_preserve_state(planning_data):
    from athena_agent.learning import MultipleChoiceAnswer
    context, store, _, _, question = started(planning_data, [])
    provider = AsyncMock()
    provider.generate.side_effect = asyncio.CancelledError()
    orchestrator = LearningOrchestrator(store, provider)
    before = store.read(context)
    with pytest.raises(ConversationError, match='current question'):
        asyncio.run(orchestrator.answer(context, MultipleChoiceAnswer(question_id='other', selected_choice_id='a')))
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(orchestrator.answer(context, MultipleChoiceAnswer(question_id=question.question.question_id, selected_choice_id='a')))
    assert store.read(context) == before


def test_learning_loop_behavior_evaluations():
    import json
    from pathlib import Path
    from athena_agent.evaluation import evaluate_fixture
    fixture = json.loads((Path(__file__).parent / 'fixtures/learning_loop.json').read_text())
    result = asyncio.run(evaluate_fixture(fixture))
    assert result['passed'] and len(result['results']) == 3
