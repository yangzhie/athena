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


def test_supported_prerequisite_gap_triggers_recheck_without_demoting_it(planning_data):
    from athena_agent.assessment import AssessmentService
    from athena_agent.learning import ConceptMastery, TextAnswer
    context, store, _, _, _ = started(planning_data, [])
    assessor = AssessmentService(store, MockLLM([OPEN]))
    question = asyncio.run(assessor.generate_open_ended(context, 'bubble-sort'))
    session = store.read(context)
    session.active_topic.current_activity = question
    session.active_topic.learning_state.mastery = [ConceptMastery(concept_id='comparison', status='mastered', assessment_ids=['historical-evidence'])]
    store._save(context, session)
    mock = MockLLM([
        {'outcome': 'incorrect', 'feedback': 'Recheck comparison.', 'confidence': 0.95, 'evidence_quotes': ['cannot compare']},
        {'misconceptions': [], 'prerequisite_gaps': [{'concept_id': 'comparison', 'status': 'supported', 'evidence_quote': 'cannot compare', 'confidence': 0.95}]}, MC,
    ])
    activity = asyncio.run(LearningOrchestrator(store, mock).answer(context, TextAnswer(question_id=question.question.question_id, text='I cannot compare 3 and 2.')))
    assert activity.kind == 'question' and activity.question.concept_id == 'comparison'
    assert store.read(context).active_topic.learning_state.mastery[0].status == 'mastered'


def test_recovery_continuation_requests_a_single_step(planning_data):
    from athena_agent.learning import MultipleChoiceAnswer
    from .test_teaching import add_selection
    context, store, _, _, question = started(planning_data, [])
    for _ in range(3):
        add_selection(context, store, concept_id='comparison')
    mock = MockLLM([{'misconceptions': [], 'prerequisite_gaps': []}, {'text': 'For [2, 1], compare these two neighbours.'}, OPEN])
    orchestrator = LearningOrchestrator(store, mock)
    teaching = asyncio.run(orchestrator.answer(context, MultipleChoiceAnswer(question_id=question.question.question_id, selected_choice_id='b')))
    assert 'worked steps' in mock.calls[1].messages[0].content
    asyncio.run(orchestrator.continue_learning(context, teaching.activity_id))
    assert '"recovery": true' in mock.calls[2].messages[1].content
    assert 'just one reasoning step' in mock.calls[2].messages[0].content


def one_concept_responses(scope='narrow'):
    return [
        {'scope': scope, 'rationale': 'One initial concept'},
        {'concepts': [{'concept_id': 'comparison', 'title': 'Comparison', 'description': 'Compare values'}], 'partial_coverage': scope == 'broad'},
        {'concepts': [{'concept_id': 'comparison', 'objectives': ['Compare two values'], 'difficulty': 'beginner'}]}, MC,
    ]


def successful_reasoning():
    return {'outcome': 'correct', 'feedback': 'Good reasoning.', 'confidence': 0.95, 'evidence_quotes': ['swap neighbours']}


def reach_reasoning(responses):
    from athena_agent.learning import MultipleChoiceAnswer
    context, store, mock, orchestrator = setup(responses)
    first = asyncio.run(orchestrator.start(context, 'Comparisons'))
    followup = asyncio.run(orchestrator.answer(context, MultipleChoiceAnswer(question_id=first.question.question_id, selected_choice_id='a')))
    return context, store, mock, orchestrator, followup


def test_narrow_topic_completes_only_after_independent_mastery():
    from athena_agent.learning import TextAnswer
    context, store, mock, orchestrator, followup = reach_reasoning([*one_concept_responses(), OPEN, successful_reasoning()])
    before = store.read(context)
    assert before.active_topic.learning_state.phase != 'complete'
    completion = asyncio.run(orchestrator.answer(context, TextAnswer(question_id=followup.question.question_id, text='Compare values and swap neighbours.')))
    topic = store.read(context).active_topic
    assert completion.kind == 'completion'
    assert topic.learning_state.phase == 'complete' and topic.learning_state.current_concept_id is None
    assert topic.learning_state.mastery[0].status == 'mastered'
    assert len(mock.calls) == 6


def broad_expansion():
    concepts = [
        {'concept_id': 'comparison', 'title': 'Comparison', 'description': 'Compare values'},
        {'concept_id': 'ordering', 'title': 'Ordering', 'description': 'Order values', 'prerequisite_ids': ['comparison']},
    ]
    return [
        {'relation': 'same_topic', 'goal': 'Comparisons', 'scope': {'scope': 'broad', 'rationale': 'More concepts'}, 'graph': {'concepts': concepts, 'partial_coverage': True}},
        {'concepts': [{'concept_id': item['concept_id'], 'objectives': ['Apply ' + item['title']], 'difficulty': 'beginner'} for item in concepts]}, MC,
    ]


def test_broad_subject_expands_instead_of_claiming_completion():
    from athena_agent.learning import TextAnswer
    context, store, _, orchestrator, followup = reach_reasoning([*one_concept_responses('broad'), OPEN, successful_reasoning(), *broad_expansion()])
    next_question = asyncio.run(orchestrator.answer(context, TextAnswer(question_id=followup.question.question_id, text='Compare values and swap neighbours.')))
    topic = store.read(context).active_topic
    assert next_question.question.concept_id == 'ordering'
    assert topic.learning_state.phase == 'diagnose' and topic.roadmap.graph.partial_coverage
    assert topic.learning_state.mastery[0].status == 'mastered'


def test_failed_broad_expansion_rolls_back_last_answer():
    from athena_agent.learning import TextAnswer
    context, store, _, orchestrator, followup = reach_reasoning([*one_concept_responses('broad'), OPEN, successful_reasoning(), DependencyError('Unavailable')])
    before = store.read(context)
    with pytest.raises(LLMError):
        asyncio.run(orchestrator.answer(context, TextAnswer(question_id=followup.question.question_id, text='Compare values and swap neighbours.')))
    assert store.read(context) == before


def test_automatic_expansion_cannot_narrow_a_broad_subject():
    from athena_agent.learning import TextAnswer
    expansion = broad_expansion()
    expansion[0]['scope']['scope'] = 'narrow'
    expansion[0]['graph']['partial_coverage'] = False
    context, store, _, orchestrator, followup = reach_reasoning([*one_concept_responses('broad'), OPEN, successful_reasoning(), *expansion])
    before = store.read(context)
    with pytest.raises(LLMError):
        asyncio.run(orchestrator.answer(context, TextAnswer(question_id=followup.question.question_id, text='Compare values and swap neighbours.')))
    assert store.read(context) == before
    assert store.read(context).active_topic.roadmap.scope.scope == 'broad'
