"""Internal assessment records and model-output contracts."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ._schema import Contract, NonBlankString
from .retrieval import SourceReference
from .learning import Answer, Assessment, AssessmentOutcome, Choice, Confidence, QuestionWithCriteria, LearningActivity


class MultipleChoiceDraft(Contract):
    prompt: NonBlankString
    choices: Annotated[list[Choice], Field(min_length=2)]
    correct_choice_id: NonBlankString
    rationale: NonBlankString

    @model_validator(mode='after')
    def valid_choices(self) -> Self:
        ids = [choice.choice_id for choice in self.choices]
        if len(set(ids)) != len(ids) or self.correct_choice_id not in ids:
            raise ValueError('Choices must be unique and contain the correct choice.')
        return self


FollowupPurpose = Literal['verification', 'application', 'retention']


class QuestionRecord(Contract):
    """Private bundle; expose only its question through QuestionActivity."""

    activity_id: NonBlankString
    bundle: QuestionWithCriteria
    parent_assessment_id: NonBlankString | None = None
    followup_purpose: FollowupPurpose = 'verification'
    sources: list[SourceReference] = Field(default_factory=list)


class OpenEndedDraft(Contract):
    prompt: NonBlankString
    expected_reasoning: NonBlankString


class AnswerSubmission(Contract):
    answer: Answer
    hint_used: bool = False


class EvaluationDraft(Contract):
    outcome: AssessmentOutcome
    feedback: NonBlankString
    confidence: Confidence
    evidence_quotes: list[NonBlankString] = Field(default_factory=list)


class MisconceptionFinding(Contract):
    description: NonBlankString
    status: Literal['suspected', 'supported']
    evidence_quote: NonBlankString
    confidence: Confidence


class PrerequisiteFinding(Contract):
    concept_id: NonBlankString
    status: Literal['suspected', 'supported']
    evidence_quote: NonBlankString
    confidence: Confidence


class Diagnosis(Contract):
    misconceptions: list[MisconceptionFinding] = Field(default_factory=list)
    prerequisite_gaps: list[PrerequisiteFinding] = Field(default_factory=list)

    @model_validator(mode='after')
    def unique_findings(self) -> Self:
        descriptions = [item.description for item in self.misconceptions]
        concepts = [item.concept_id for item in self.prerequisite_gaps]
        if len(set(descriptions)) != len(descriptions) or len(set(concepts)) != len(concepts):
            raise ValueError('Diagnosis findings must be unique.')
        return self


class AssessmentRecord(Contract):
    answer: Answer
    assessment: Assessment
    hint_used: bool = False
    evidence_quotes: list[NonBlankString] = Field(default_factory=list)
    diagnosis: Diagnosis | None = None
    next_activity: LearningActivity | None = None

    @model_validator(mode='after')
    def matching_question(self) -> Self:
        if self.answer.question_id != self.assessment.question_id:
            raise ValueError('Answer and assessment must reference the same question.')
        return self


class AssessmentPolicy(Contract):
    evaluation_confidence_threshold: Confidence = 0.8
