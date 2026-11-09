"""Learner-facing progress projections derived from stored evidence."""

from typing import Literal

from pydantic import Field

from ._schema import Contract, NonBlankString
from .conversation import ConversationError, TopicContext
from .learning import ExplanationActivity, LearningPhase, MasteryStatus, QuestionActivity


class ConceptProgress(Contract):
    concept_id: NonBlankString
    title: NonBlankString
    status: MasteryStatus
    evidence_count: int = Field(ge=0)


class ProgressSummary(Contract):
    goal: NonBlankString
    phase: LearningPhase
    current_concept_id: NonBlankString | None
    concepts: list[ConceptProgress]
    mastered_count: int = Field(ge=0)
    total_count: int = Field(ge=0)
    eligible_concept_ids: list[NonBlankString]
    partial_coverage: bool
    complete: bool
    next_step: Literal['answer', 'continue', 'plan', 'expand', 'complete']


def summarize_progress(topic: TopicContext) -> ProgressSummary:
    if topic.roadmap is None:
        raise ConversationError('An active learning roadmap is required.')
    mastery = {item.concept_id: item for item in topic.learning_state.mastery}
    concepts = [ConceptProgress(
        concept_id=concept.concept_id, title=concept.title,
        status=mastery[concept.concept_id].status if concept.concept_id in mastery else 'unknown',
        evidence_count=len(mastery[concept.concept_id].assessment_ids) if concept.concept_id in mastery else 0,
    ) for concept in topic.roadmap.graph.concepts]
    mastered = sum(item.status == 'mastered' for item in concepts)
    complete = (topic.learning_state.phase == 'complete' and mastered == len(concepts)
                and topic.roadmap.scope.scope == 'narrow' and not topic.roadmap.graph.partial_coverage)
    if complete:
        next_step = 'complete'
    elif isinstance(topic.current_activity, QuestionActivity):
        next_step = 'answer'
    elif isinstance(topic.current_activity, ExplanationActivity):
        next_step = 'continue'
    elif mastered == len(concepts):
        next_step = 'expand'
    else:
        next_step = 'plan'
    return ProgressSummary(
        goal=topic.learning_state.goal, phase=topic.learning_state.phase,
        current_concept_id=topic.learning_state.current_concept_id, concepts=concepts,
        mastered_count=mastered, total_count=len(concepts),
        eligible_concept_ids=topic.roadmap.eligible_concept_ids(topic.learning_state),
        partial_coverage=topic.roadmap.graph.partial_coverage,
        complete=complete, next_step=next_step,
    )
