from athena_agent.adaptation import adjust_learning
from athena_agent.assessment import AssessmentService
from athena_agent.learning import MultipleChoiceAnswer
from athena_agent.llm import MockLLM
import asyncio

from .test_teaching import gap, add_selection
from .test_assessment import assessed_topic, MC
from .test_session_planning import planning_data


def test_repeated_failures_lower_difficulty_and_reduce_pacing(gap):
    context, store, _ = gap
    add_selection(context, store)
    before = store.read(context)
    adjustment = adjust_learning(before.active_topic, 'bubble-sort')
    assert adjustment.difficulty == 'beginner'
    assert adjustment.depth == 'scaffolded' and adjustment.pacing == 'one_unit'
    assert store.read(context) == before
    add_selection(context, store, correct=True)
    adjustment = adjust_learning(store.read(context).active_topic, 'bubble-sort')
    assert adjustment.difficulty == 'intermediate' and adjustment.pacing == 'application'


def test_two_unhinted_successes_raise_difficulty_without_claiming_mastery(assessed_topic):
    context, store = assessed_topic
    add_selection(context, store, correct=True)
    add_selection(context, store, correct=True)
    topic = store.read(context).active_topic
    assert adjust_learning(topic, 'bubble-sort').difficulty == 'advanced'
    assert topic.learning_state.mastery[0].status == 'developing'
    topic.assessment_records[-1].hint_used = True
    assert adjust_learning(topic, 'bubble-sort').difficulty == 'intermediate'
    topic.assessment_records[-1].assessment.outcome = 'uncertain'
    assert adjust_learning(topic, 'bubble-sort').difficulty == 'intermediate'


def test_orchestrated_application_uses_lower_difficulty_after_struggles(planning_data):
    from athena_agent.orchestrator import LearningOrchestrator
    from .test_orchestrator import started, OPEN
    planning_data[2]['concepts'][0]['difficulty'] = 'intermediate'
    context, store, _, orchestrator, question = started(planning_data, [
        {'misconceptions': [], 'prerequisite_gaps': []}, {'text': 'Compare adjacent values.'}, OPEN,
    ])
    # A prior independently recorded diagnostic failure is not fabricated mastery.
    add_selection(context, store, concept_id='comparison')
    activity = asyncio.run(orchestrator.answer(context, MultipleChoiceAnswer(question_id=question.question.question_id, selected_choice_id='b')))
    followup = asyncio.run(orchestrator.continue_learning(context, activity.activity_id))
    assert followup.question.difficulty == 'beginner'
    assert store.read(context).active_topic.learning_state.mastery[0].status == 'developing'
