"""Deterministic learning-action selection from topic-local evidence."""

from typing import Literal

from ._schema import Contract, NonBlankString
from .adaptation import adjust_learning
from .learning import Difficulty
from .conversation import ConversationError, TopicContext


class LearningDecision(Contract):
    action: Literal['teach', 'verify', 'diagnose', 'progress', 'recover']
    concept_id: NonBlankString | None
    reason: NonBlankString
    difficulty: Difficulty | None = None


def _select_action(topic: TopicContext, assessment_id: str) -> LearningDecision:
    if topic.roadmap is None:
        raise ConversationError('An active learning roadmap is required.')
    record = next((item for item in topic.assessment_records if item.assessment.assessment_id == assessment_id), None)
    if record is None:
        raise ConversationError('The assessment is not available in the active topic.')
    assessment = record.assessment
    concepts = {item.concept_id: item for item in topic.roadmap.graph.concepts}
    concept = concepts.get(assessment.concept_id)
    if concept is None:
        raise ConversationError('The concept is not in the active roadmap.')
    mastered = {item.concept_id for item in topic.learning_state.mastery if item.status == 'mastered'}
    eligible = topic.roadmap.eligible_concept_ids(topic.learning_state)
    missing = set(concept.prerequisite_ids) - mastered
    if missing:
        ancestors = set()
        pending = list(missing)
        while pending:
            key = pending.pop()
            if key not in ancestors:
                ancestors.add(key)
                pending.extend(concepts[key].prerequisite_ids)
        target = next((key for key in eligible if key in ancestors), None)
        if target is None:
            raise ConversationError('Prerequisite evidence is inconsistent; revise the roadmap.')
        return LearningDecision(action='diagnose', concept_id=target, reason='Assess a missing prerequisite before continuing the dependent concept.')
    if record.diagnosis is not None and assessment.outcome in {'partial', 'incorrect'}:
        gaps = [item.concept_id for item in record.diagnosis.prerequisite_gaps if item.status == 'supported' and item.confidence >= 0.8]
        for gap in gaps:
            if gap in concepts and set(concepts[gap].prerequisite_ids) <= mastered:
                return LearningDecision(action='diagnose', concept_id=gap, reason='Recheck a supported prerequisite gap without assuming its mastery has changed.')
    failures = 0
    for item in reversed(topic.assessment_records):
        if item.assessment.concept_id != concept.concept_id or item.assessment.outcome == 'uncertain' or item.assessment.confidence < 0.8:
            continue
        if item.assessment.outcome == 'correct':
            break
        failures += 1
    if assessment.outcome != 'correct' and failures >= 4:
        return LearningDecision(action='recover', concept_id=concept.concept_id, reason='Reset repeated unsuccessful attempts with a simpler worked example and single-step check.')
    if assessment.outcome != 'correct':
        return LearningDecision(action='teach', concept_id=concept.concept_id, reason='Clarify the assessed gap before another application check.')
    if concept.concept_id not in mastered:
        return LearningDecision(action='verify', concept_id=concept.concept_id, reason='Correctness alone does not establish independent understanding.')
    if eligible:
        return LearningDecision(action='diagnose', concept_id=eligible[0], reason='Advance to an unmastered concept with demonstrated prerequisites.')
    return LearningDecision(action='progress', concept_id=None, reason='All concepts in the current roadmap have supporting mastery evidence.')


def select_action(topic: TopicContext, assessment_id: str) -> LearningDecision:
    decision = _select_action(topic, assessment_id)
    if decision.concept_id is not None:
        decision.difficulty = adjust_learning(topic, decision.concept_id).difficulty
    return decision
