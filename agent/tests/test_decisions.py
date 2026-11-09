import asyncio

import pytest

from athena_agent.assessment import AssessmentService
from athena_agent.conversation import ConversationError
from athena_agent.decisions import select_action
from athena_agent.learning import ConceptMastery, MultipleChoiceAnswer
from athena_agent.llm import MockLLM
from .test_assessment import MC, assessed_topic
from .test_session_planning import planning_data


def evidence(context, store, concept_id='bubble-sort', choice='a'):
    assessor = AssessmentService(store, MockLLM([MC]))
    question = asyncio.run(assessor.generate_multiple_choice(context, concept_id))
    return asyncio.run(assessor.evaluate(context, MultipleChoiceAnswer(question_id=question.question.question_id, selected_choice_id=choice)))


def test_missing_prerequisite_is_diagnosed_before_dependent_verification(assessed_topic):
    context, store = assessed_topic
    assessment = evidence(context, store)
    topic = store.read(context).active_topic
    before = topic.model_dump()
    decision = select_action(topic, assessment.assessment_id)
    assert decision.action == 'diagnose' and decision.concept_id == 'comparison'
    assert topic.model_dump() == before
    topic.learning_state.mastery.append(ConceptMastery(concept_id='comparison', status='mastered', assessment_ids=['external-evidence']))
    assert select_action(topic, assessment.assessment_id).action == 'verify'


def test_gap_teaches_then_mastery_advances_only_eligible_concepts(assessed_topic):
    context, store = assessed_topic
    assessment = evidence(context, store, 'comparison', 'b')
    topic = store.read(context).active_topic
    assert select_action(topic, assessment.assessment_id).action == 'teach'
    topic.assessment_records[-1].assessment.outcome = 'correct'
    topic.learning_state.mastery[0].status = 'mastered'
    decision = select_action(topic, assessment.assessment_id)
    assert decision.action == 'diagnose' and decision.concept_id == 'bubble-sort'
    topic.learning_state.mastery.append(ConceptMastery(concept_id='bubble-sort', status='mastered', assessment_ids=['e']))
    assert select_action(topic, assessment.assessment_id).action == 'progress'
    with pytest.raises(ConversationError, match='assessment'):
        select_action(topic, 'missing')
