import asyncio
from copy import deepcopy

import pytest

from athena_agent.conversation import ConversationError
from athena_agent.learning import MultipleChoiceAnswer, TextAnswer
from athena_agent.llm import DependencyError, LLMError
from .test_assessment import assessed_topic, service
from .test_evaluation import GRADE, TEXT, make_question
from .test_session_planning import planning_data


DIAGNOSIS = {
    'misconceptions': [{'description': 'The comparison rule is unclear.', 'status': 'suspected', 'evidence_quote': 'Adjacent comparisons', 'confidence': 0.7}],
    'prerequisite_gaps': [{'concept_id': 'comparison', 'status': 'suspected', 'evidence_quote': 'Adjacent comparisons', 'confidence': 0.7}],
}


def evaluate_written(context, store, outcome='partial'):
    question = make_question(context, store)
    assessor, _ = service(store, [{**GRADE, 'outcome': outcome}])
    return asyncio.run(assessor.evaluate(context, TextAnswer(question_id=question.question_id, text=TEXT)))


def test_diagnosis_preserves_grade_and_marks_suspected_summaries(assessed_topic):
    context, store = assessed_topic
    assessment = evaluate_written(context, store)
    assessor, mock = service(store, [DIAGNOSIS])
    before = store.read(context)
    diagnosis = asyncio.run(assessor.diagnose(context, assessment.assessment_id))
    after = store.read(context)
    stored = after.active_topic.assessment_records[0].assessment
    assert stored.outcome == assessment.outcome
    assert stored.confidence == assessment.confidence
    assert stored.feedback == assessment.feedback
    assert stored.misconceptions == ['suspected: The comparison rule is unclear.']
    assert stored.prerequisite_gaps == ['comparison']
    assert after.active_topic.learning_state == before.active_topic.learning_state
    assert asyncio.run(assessor.diagnose(context, assessment.assessment_id)) == diagnosis
    assert len(mock.calls) == 1
    assert store.read(context) == after
    diagnosis.misconceptions.clear()
    assert len(store.read(context).active_topic.assessment_records[0].diagnosis.misconceptions) == 1


@pytest.mark.parametrize('change', ['invented_quote', 'unrelated_gap', 'self_gap', 'unsupported_confidence'])
def test_invalid_findings_leave_assessment_untouched(assessed_topic, change):
    context, store = assessed_topic
    assessment = evaluate_written(context, store)
    findings = deepcopy(DIAGNOSIS)
    if change == 'invented_quote':
        findings['misconceptions'][0]['evidence_quote'] = 'The learner never said this'
    elif change == 'unrelated_gap':
        findings['prerequisite_gaps'][0]['concept_id'] = 'unrelated'
    elif change == 'self_gap':
        findings['prerequisite_gaps'][0]['concept_id'] = 'bubble-sort'
    else:
        findings['misconceptions'][0]['status'] = 'supported'
    assessor, _ = service(store, [findings])
    before = store.read(context)
    with pytest.raises(LLMError):
        asyncio.run(assessor.diagnose(context, assessment.assessment_id))
    assert store.read(context) == before


def test_selection_alone_cannot_support_definitive_misconception(assessed_topic):
    context, store = assessed_topic
    question = make_question(context, store, 'multiple_choice')
    assessor, _ = service(store, [])
    assessment = asyncio.run(assessor.evaluate(context, MultipleChoiceAnswer(question_id=question.question_id, selected_choice_id='b')))
    findings = {'misconceptions': [{'description': 'Swaps can be random.', 'status': 'supported', 'evidence_quote': 'Any random pair', 'confidence': 1.0}]}
    assessor, _ = service(store, [findings])
    before = store.read(context)
    with pytest.raises(LLMError):
        asyncio.run(assessor.diagnose(context, assessment.assessment_id))
    assert store.read(context) == before
    findings['misconceptions'][0]['status'] = 'suspected'
    assessor, _ = service(store, [findings])
    assert asyncio.run(assessor.diagnose(context, assessment.assessment_id)).misconceptions[0].status == 'suspected'


def test_supported_written_findings_require_decisive_incorrect_evidence(assessed_topic):
    context, store = assessed_topic
    assessment = evaluate_written(context, store, outcome='incorrect')
    findings = deepcopy(DIAGNOSIS)
    findings['misconceptions'][0].update(status='supported', confidence=0.95)
    assessor, _ = service(store, [findings])
    assert asyncio.run(assessor.diagnose(context, assessment.assessment_id)).misconceptions[0].status == 'supported'


def test_empty_diagnosis_and_failures_are_distinct(assessed_topic):
    context, store = assessed_topic
    assessment = evaluate_written(context, store)
    assessor, _ = service(store, [DependencyError('Unavailable')])
    before = store.read(context)
    with pytest.raises(LLMError):
        asyncio.run(assessor.diagnose(context, assessment.assessment_id))
    assert store.read(context) == before
    assessor, _ = service(store, [{}])
    diagnosis = asyncio.run(assessor.diagnose(context, assessment.assessment_id))
    assert diagnosis.misconceptions == diagnosis.prerequisite_gaps == []


def test_missing_assessment_never_calls_model(assessed_topic):
    context, store = assessed_topic
    assessor, mock = service(store, [])
    with pytest.raises(ConversationError, match='assessment'):
        asyncio.run(assessor.diagnose(context, 'missing'))
    assert mock.calls == []
