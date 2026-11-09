"""Transparent evidence rules for concept mastery; no model judgement or progression."""

from typing import Annotated, Self, Sequence

from pydantic import Field, model_validator

from ._schema import Contract
from .assessment_models import AssessmentRecord, QuestionRecord
from .learning import ConceptMastery, Confidence, OpenEndedQuestion


class MasteryPolicy(Contract):
    confidence_threshold: Confidence = 0.8
    required_successes: Annotated[int, Field(ge=2)] = 2
    required_reasoning_successes: Annotated[int, Field(ge=1)] = 1

    @model_validator(mode='after')
    def possible_reasoning_threshold(self) -> Self:
        if self.required_reasoning_successes > self.required_successes:
            raise ValueError('Reasoning threshold cannot exceed the success threshold.')
        return self


def derive_mastery(
    concept_id: str, questions: Sequence[QuestionRecord], assessments: Sequence[AssessmentRecord],
    *, policy: MasteryPolicy, previous: ConceptMastery | None = None,
) -> ConceptMastery:
    relevant = [record for record in assessments if record.assessment.concept_id == concept_id]
    references = list(previous.assessment_ids) if previous is not None else []
    for record in relevant:
        if record.assessment.assessment_id not in references:
            references.append(record.assessment.assessment_id)
    decisive = [record for record in relevant if
        record.assessment.confidence >= policy.confidence_threshold
        and record.assessment.outcome != 'uncertain'
    ]
    status = previous.status if previous is not None else 'unknown'
    if decisive:
        status = 'developing'
        recent = decisive[-policy.required_successes:]
        by_id = {record.bundle.question.question_id: record.bundle.question for record in questions}
        if len(recent) == policy.required_successes and all(
            record.assessment.outcome == 'correct' and not record.hint_used for record in recent
        ):
            selected = [by_id.get(record.assessment.question_id) for record in recent]
            signatures = {' '.join(question.prompt.split()).casefold() for question in selected if question is not None}
            reasoning = sum(isinstance(question, OpenEndedQuestion) for question in selected)
            if len(signatures) == len(recent) and reasoning >= policy.required_reasoning_successes:
                status = 'mastered'
    return ConceptMastery(concept_id=concept_id, status=status, assessment_ids=references)
