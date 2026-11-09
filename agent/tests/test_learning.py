"""Learning contract boundaries and learner-facing serialization."""

import json

import pytest
from pydantic import TypeAdapter, ValidationError

from athena_agent.contracts import AgentRequest, RequestContext, SuccessResponse
from athena_agent.learning import (
    Answer, Assessment, CompletionActivity, ConceptMastery, ExplanationActivity,
    FeedbackActivity, HintActivity, LearningActivity, LearningState,
    MultipleChoiceAnswer, MultipleChoiceCriteria, MultipleChoiceQuestion,
    OpenEndedCriteria, OpenEndedQuestion, Question, QuestionActivity,
    QuestionWithCriteria, TextAnswer,
)


@pytest.fixture
def question_data():
    return {
        "kind": "multiple_choice", "question_id": "q1", "concept_id": "sorting",
        "prompt": "Which pair is swapped?", "difficulty": "beginner",
        "choices": [
            {"choice_id": "a", "text": "Adjacent out-of-order items"},
            {"choice_id": "b", "text": "Random items"},
        ],
    }


@pytest.fixture
def bundle(question_data):
    return QuestionWithCriteria(
        question=question_data,
        criteria=MultipleChoiceCriteria(correct_choice_id="a", rationale="Compare neighbours."),
    )


def test_questions_and_internal_criteria_round_trip(bundle):
    assert QuestionWithCriteria.model_validate_json(bundle.model_dump_json()) == bundle
    open_question = OpenEndedQuestion(
        question_id='q2', concept_id='sorting', prompt='Explain a sorting pass.',
        difficulty='intermediate',
    )
    open_bundle = QuestionWithCriteria(
        question=open_question,
        criteria=OpenEndedCriteria(expected_reasoning='Compare adjacent items throughout the pass.'),
    )
    assert QuestionWithCriteria.model_validate_json(open_bundle.model_dump_json()) == open_bundle
    adapter = TypeAdapter(Question)
    for question in [bundle.question, open_question]:
        assert adapter.validate_json(adapter.dump_json(question)) == question


def test_question_activity_does_not_expose_criteria(bundle):
    response = SuccessResponse[QuestionActivity](
        request_id='r1', data=QuestionActivity(activity_id='activity-1', question=bundle.question),
    )
    serialized = response.model_dump_json()
    for secret in ['correct_choice_id', 'rationale', 'expected_reasoning', 'criteria']:
        assert secret not in serialized
    assert 'criteria' not in QuestionActivity.model_json_schema()['properties']
    with pytest.raises(ValidationError):
        QuestionActivity.model_validate({
            'activity_id': 'a1', 'question': bundle.question, 'criteria': bundle.criteria,
        })


@pytest.mark.parametrize('choices', [[], [{'choice_id': 'a', 'text': 'Only one'}], [
    {'choice_id': 'a', 'text': 'One'}, {'choice_id': 'a', 'text': 'Two'},
]])
def test_invalid_choices_are_rejected(question_data, choices):
    with pytest.raises(ValidationError):
        MultipleChoiceQuestion.model_validate({**question_data, 'choices': choices})


def test_correct_choice_must_exist(question_data):
    with pytest.raises(ValidationError):
        QuestionWithCriteria(
            question=question_data,
            criteria=MultipleChoiceCriteria(correct_choice_id='missing', rationale='Reason'),
        )


def test_criteria_must_match_format(question_data):
    with pytest.raises(ValidationError):
        QuestionWithCriteria(
            question=question_data,
            criteria=OpenEndedCriteria(expected_reasoning='Reason'),
        )


@pytest.mark.parametrize('field,value', [
    ('question_id', ' '), ('concept_id', ''), ('prompt', '\n'),
    ('difficulty', 'impossible'), ('question_id', 123), ('unknown', True),
])
def test_question_validation(question_data, field, value):
    with pytest.raises(ValidationError):
        MultipleChoiceQuestion.model_validate({**question_data, field: value})


def test_answers_work_in_request_envelopes():
    context = RequestContext(request_id='r1', learner_id='l1')
    for answer in [
        MultipleChoiceAnswer(question_id='q1', selected_choice_id='a'),
        TextAnswer(question_id='q2', text='Compare adjacent items.'),
    ]:
        request = AgentRequest[Answer](context=context, payload=answer)
        assert AgentRequest[Answer].model_validate_json(request.model_dump_json()) == request


@pytest.mark.parametrize('value', [
    {'kind': 'multiple_choice', 'question_id': 'q1', 'selected_choice_id': ''},
    {'kind': 'text', 'question_id': 'q1', 'text': ' '},
    {'kind': 'unknown', 'question_id': 'q1', 'text': 'Hi'},
])
def test_invalid_answers(value):
    with pytest.raises(ValidationError):
        TypeAdapter(Answer).validate_python(value)


@pytest.fixture
def assessment_data():
    return {
        'assessment_id': 'e1', 'question_id': 'q1', 'concept_id': 'sorting',
        'outcome': 'partial', 'feedback': 'Explain why adjacent items matter.',
        'confidence': 0.7, 'misconceptions': ['Swaps are random.'],
        'prerequisite_gaps': ['comparison'],
    }


def test_assessment_and_state_round_trip(assessment_data):
    evidence = Assessment.model_validate(assessment_data)
    assert Assessment.model_validate_json(evidence.model_dump_json()) == evidence
    state = LearningState(
        goal='Understand Bubble Sort', phase='reinforce', current_concept_id='sorting',
        mastery=[ConceptMastery(concept_id='sorting', status='developing', assessment_ids=['e1'])],
    )
    assert LearningState.model_validate_json(state.model_dump_json()) == state


@pytest.mark.parametrize('confidence', [-0.1, 1.1, float('nan'), float('inf'), '0.5', True])
def test_assessment_confidence_validation(assessment_data, confidence):
    with pytest.raises(ValidationError):
        Assessment.model_validate({**assessment_data, 'confidence': confidence})


@pytest.mark.parametrize('outcome', ['correct', 'partial', 'incorrect', 'uncertain'])
def test_assessment_outcomes(assessment_data, outcome):
    assert Assessment.model_validate({**assessment_data, 'outcome': outcome}).outcome == outcome


def test_invalid_outcome(assessment_data):
    with pytest.raises(ValidationError):
        Assessment.model_validate({**assessment_data, 'outcome': 'maybe'})


def test_mastery_requires_evidence():
    with pytest.raises(ValidationError):
        ConceptMastery(concept_id='sorting', status='mastered')
    assert ConceptMastery(
        concept_id='sorting', status='mastered', assessment_ids=['e1'],
    ).status == 'mastered'


def test_state_defaults_are_independent():
    first = LearningState(goal='Sorting')
    second = LearningState(goal='Graphs')
    first.mastery.append(ConceptMastery(concept_id='sorting'))
    assert second.mastery == []
    assert second.phase == 'diagnose'
    assert second.current_concept_id is None


def test_duplicate_evidence_and_concepts_are_rejected():
    with pytest.raises(ValidationError):
        ConceptMastery(concept_id='sorting', assessment_ids=['e1', 'e1'])
    with pytest.raises(ValidationError):
        LearningState(goal='Sorting', mastery=[
            ConceptMastery(concept_id='sorting'), ConceptMastery(concept_id='sorting'),
        ])


@pytest.mark.parametrize('data', [{'goal': ' '}, {'goal': 'Sorting', 'phase': 'unknown'}])
def test_invalid_state(data):
    with pytest.raises(ValidationError):
        LearningState.model_validate(data)


def test_all_activities_round_trip_and_generate_schema(bundle):
    activities = [
        QuestionActivity(activity_id='a1', question=bundle.question),
        ExplanationActivity(activity_id='a2', concept_id='sorting', text='Compare neighbours.'),
        HintActivity(activity_id='a3', question_id='q1', text='Look at adjacent items.'),
        FeedbackActivity(activity_id='a4', question_id='q1', text='Good reasoning.'),
        CompletionActivity(activity_id='a5', text='You have demonstrated understanding.'),
    ]
    adapter = TypeAdapter(LearningActivity)
    for activity in activities:
        response = SuccessResponse[LearningActivity](request_id='r1', data=activity)
        assert SuccessResponse[LearningActivity].model_validate_json(response.model_dump_json()) == response
    schema = adapter.json_schema()
    assert set(schema['discriminator']['mapping']) == {
        'question', 'explanation', 'hint', 'feedback', 'completion',
    }
    json.dumps(SuccessResponse[LearningActivity].model_json_schema())
    json.dumps(AgentRequest[Answer].model_json_schema())
    json.dumps(QuestionWithCriteria.model_json_schema())
    json.dumps(LearningState.model_json_schema())


@pytest.mark.parametrize('data', [
    {'kind': 'animation', 'activity_id': 'a1', 'text': 'Hi'},
    {'kind': 'completion', 'activity_id': 'a1', 'text': ' '},
    {'kind': 'completion', 'activity_id': 'a1', 'text': 'Done', 'script': 'run()'},
])
def test_invalid_activities(data):
    with pytest.raises(ValidationError):
        TypeAdapter(LearningActivity).validate_python(data)
