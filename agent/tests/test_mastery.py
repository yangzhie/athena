import asyncio

import pytest
from pydantic import ValidationError

from athena_agent.assessment_models import AssessmentRecord, QuestionRecord
from athena_agent.learning import (
    Assessment, ConceptMastery, OpenEndedCriteria, OpenEndedQuestion,
    QuestionWithCriteria, TextAnswer, MultipleChoiceAnswer,
)
from athena_agent.mastery import MasteryPolicy, derive_mastery
from .test_assessment import assessed_topic, service
from .test_evaluation import TEXT, GRADE, make_question
from .test_session_planning import planning_data


def evidence(outcomes, *, hints=None, confidences=None, prompts=None):
    questions, assessments = [], []
    for index, outcome in enumerate(outcomes):
        key = f'q{index}'
        questions.append(QuestionRecord(activity_id=f'a{index}', bundle=QuestionWithCriteria(
            question=OpenEndedQuestion(question_id=key, concept_id='sorting', prompt=prompts[index] if prompts else f'Apply the concept to example {index}', difficulty='beginner'),
            criteria=OpenEndedCriteria(expected_reasoning='Explain the comparisons.'),
        )))
        assessments.append(AssessmentRecord(
            answer=TextAnswer(question_id=key, text='Reasoning'),
            assessment=Assessment(assessment_id=f'e{index}', question_id=key, concept_id='sorting', outcome=outcome, feedback='Feedback', confidence=confidences[index] if confidences else 0.9),
            hint_used=hints[index] if hints else False,
        ))
    return questions, assessments


@pytest.mark.parametrize('outcomes,status', [
    ([], 'unknown'), (['uncertain'], 'unknown'), (['correct'], 'developing'),
    (['correct', 'correct'], 'mastered'), (['correct', 'partial'], 'developing'),
    (['correct', 'correct', 'incorrect'], 'developing'),
    (['incorrect', 'correct', 'correct'], 'mastered'),
    (['correct', 'correct', 'uncertain'], 'mastered'),
])
def test_evidence_policy(outcomes, status):
    questions, assessments = evidence(outcomes)
    result = derive_mastery('sorting', questions, assessments, policy=MasteryPolicy())
    assert result.status == status
    assert result.assessment_ids == [f'e{index}' for index in range(len(outcomes))]


def test_hint_assistance_and_duplicate_prompts_do_not_prove_mastery():
    questions, records = evidence(['correct', 'correct'], hints=[False, True])
    assert derive_mastery('sorting', questions, records, policy=MasteryPolicy()).status == 'developing'
    questions, records = evidence(['correct', 'correct'], prompts=['Explain this', ' Explain THIS '])
    assert derive_mastery('sorting', questions, records, policy=MasteryPolicy()).status == 'developing'


def test_uncertain_or_low_confidence_evidence_never_demotes_previous_mastery():
    previous = ConceptMastery(concept_id='sorting', status='mastered', assessment_ids=['historical'])
    for outcomes, confidences in [(['uncertain'], [0.9]), (['incorrect'], [0.5])]:
        questions, records = evidence(outcomes, confidences=confidences)
        result = derive_mastery('sorting', questions, records, policy=MasteryPolicy(), previous=previous)
        assert result.status == 'mastered'
        assert result.assessment_ids == ['historical', 'e0']


def test_configurable_threshold_and_success_count():
    questions, records = evidence(['correct', 'correct', 'correct'])
    policy = MasteryPolicy(required_successes=3, required_reasoning_successes=2)
    assert derive_mastery('sorting', questions[:2], records[:2], policy=policy).status == 'developing'
    assert derive_mastery('sorting', questions, records, policy=policy).status == 'mastered'
    assert derive_mastery('sorting', questions, records, policy=MasteryPolicy(confidence_threshold=0.95)).status == 'unknown'


@pytest.mark.parametrize('values', [
    {'required_successes': 1}, {'required_reasoning_successes': 0},
    {'required_successes': 2, 'required_reasoning_successes': 3}, {'confidence_threshold': 1.1},
])
def test_invalid_policy(values):
    with pytest.raises(ValidationError):
        MasteryPolicy(**values)


def test_evaluation_updates_mastery_atomically_and_retries_do_not_inflate(assessed_topic):
    context, store = assessed_topic
    mc = make_question(context, store, 'multiple_choice')
    assessor, mock = service(store, [])
    selected = MultipleChoiceAnswer(question_id=mc.question_id, selected_choice_id='a')
    first = asyncio.run(assessor.evaluate(context, selected))
    assert store.read(context).active_topic.learning_state.mastery[0].status == 'developing'
    opened = make_question(context, store)
    assessor, mock = service(store, [GRADE])
    before = store.read(context)
    answer = TextAnswer(question_id=opened.question_id, text=TEXT)
    second = asyncio.run(assessor.evaluate(context, answer))
    after = store.read(context)
    mastery = after.active_topic.learning_state.mastery[0]
    assert mastery.status == 'mastered'
    assert mastery.assessment_ids == [first.assessment_id, second.assessment_id]
    assert after.active_topic.learning_state.phase == before.active_topic.learning_state.phase
    assert after.revision == before.revision + 1
    assert asyncio.run(assessor.evaluate(context, answer)) == second
    assert store.read(context) == after
    assert len(mock.calls) == 1


def test_multiple_choice_successes_alone_never_establish_mastery(assessed_topic):
    context, store = assessed_topic
    assessor, _ = service(store, [])
    for _ in range(2):
        question = make_question(context, store, 'multiple_choice')
        asyncio.run(assessor.evaluate(context, MultipleChoiceAnswer(question_id=question.question_id, selected_choice_id='a')))
    assert store.read(context).active_topic.learning_state.mastery[0].status == 'developing'


def test_explicit_recompute_is_idempotent_and_preserves_historical_refs(assessed_topic):
    context, store = assessed_topic
    question = make_question(context, store)
    assessor, _ = service(store, [GRADE])
    assessment = asyncio.run(assessor.evaluate(context, TextAnswer(question_id=question.question_id, text=TEXT)))
    snapshot = store.read(context)
    snapshot.active_topic.learning_state.mastery[0].assessment_ids.insert(0, 'historical')
    store._save(context, snapshot)
    state = asyncio.run(assessor.recompute_mastery(context))
    assert state.mastery[0].assessment_ids == ['historical', assessment.assessment_id]
    saved = store.read(context)
    assert asyncio.run(assessor.recompute_mastery(context)) == state
    assert store.read(context) == saved
    assert any(item.concept_id == 'comparison' and item.status == 'unknown' for item in state.mastery)
