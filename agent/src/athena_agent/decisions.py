"""Deterministic learning-action selection from topic-local evidence."""

from typing import Literal

from ._schema import Contract, NonBlankString
from .conversation import ConversationError, TopicContext


class LearningDecision(Contract):
    action: Literal['teach', 'verify', 'diagnose', 'progress']
    concept_id: NonBlankString | None
    reason: NonBlankString


def select_action(topic: TopicContext, assessment_id: str) -> LearningDecision:
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
    if assessment.outcome != 'correct':
        return LearningDecision(action='teach', concept_id=concept.concept_id, reason='Clarify the assessed gap before another application check.')
    if concept.concept_id not in mastered:
        return LearningDecision(action='verify', concept_id=concept.concept_id, reason='Correctness alone does not establish independent understanding.')
    if eligible:
        return LearningDecision(action='diagnose', concept_id=eligible[0], reason='Advance to an unmastered concept with demonstrated prerequisites.')
    return LearningDecision(action='progress', concept_id=None, reason='All concepts in the current roadmap have supporting mastery evidence.')
