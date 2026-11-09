"""Learning domain contracts; no generation, scoring, or progression logic."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ._schema import Contract, NonBlankString
from .retrieval import SourceAttribution

__all__ = [
    'Difficulty', 'AssessmentOutcome', 'LearningPhase', 'MasteryStatus',
    'Choice', 'MultipleChoiceQuestion', 'OpenEndedQuestion', 'Question',
    'MultipleChoiceCriteria', 'OpenEndedCriteria', 'AssessmentCriteria',
    'QuestionWithCriteria', 'MultipleChoiceAnswer', 'TextAnswer', 'Answer',
    'Assessment', 'ConceptMastery', 'LearningState', 'QuestionActivity',
    'ExplanationActivity', 'HintActivity', 'FeedbackActivity',
    'CompletionActivity', 'LearningActivity',
]

Difficulty = Literal['beginner', 'intermediate', 'advanced']
AssessmentOutcome = Literal['correct', 'partial', 'incorrect', 'uncertain']
LearningPhase = Literal['diagnose', 'teach', 'reinforce', 'evaluate', 'progress', 'complete']
MasteryStatus = Literal['unknown', 'developing', 'mastered']
Confidence = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class Choice(Contract):
    choice_id: NonBlankString
    text: NonBlankString


class _Question(Contract):
    question_id: NonBlankString
    concept_id: NonBlankString
    prompt: NonBlankString
    difficulty: Difficulty


class MultipleChoiceQuestion(_Question):
    kind: Literal['multiple_choice'] = 'multiple_choice'
    choices: Annotated[list[Choice], Field(min_length=2)]

    @model_validator(mode='after')
    def unique_choice_ids(self) -> Self:
        ids = [choice.choice_id for choice in self.choices]
        if len(set(ids)) != len(ids):
            raise ValueError('Choice IDs must be unique.')
        return self


class OpenEndedQuestion(_Question):
    kind: Literal['open_ended'] = 'open_ended'


Question = Annotated[MultipleChoiceQuestion | OpenEndedQuestion, Field(discriminator='kind')]


class MultipleChoiceCriteria(Contract):
    kind: Literal['multiple_choice'] = 'multiple_choice'
    correct_choice_id: NonBlankString
    rationale: NonBlankString


class OpenEndedCriteria(Contract):
    kind: Literal['open_ended'] = 'open_ended'
    expected_reasoning: NonBlankString


AssessmentCriteria = Annotated[
    MultipleChoiceCriteria | OpenEndedCriteria, Field(discriminator='kind')
]


class QuestionWithCriteria(Contract):
    """Agent-internal question bundle; never send its criteria to the learner."""

    question: Question
    criteria: AssessmentCriteria

    @model_validator(mode='after')
    def matching_criteria(self) -> Self:
        if self.question.kind != self.criteria.kind:
            raise ValueError('Criteria must match the question format.')
        if isinstance(self.question, MultipleChoiceQuestion) and isinstance(
            self.criteria, MultipleChoiceCriteria
        ):
            if self.criteria.correct_choice_id not in {
                choice.choice_id for choice in self.question.choices
            }:
                raise ValueError('Correct choice must reference an existing choice.')
        return self


class MultipleChoiceAnswer(Contract):
    kind: Literal['multiple_choice'] = 'multiple_choice'
    question_id: NonBlankString
    selected_choice_id: NonBlankString


class TextAnswer(Contract):
    kind: Literal['text'] = 'text'
    question_id: NonBlankString
    text: NonBlankString


Answer = Annotated[MultipleChoiceAnswer | TextAnswer, Field(discriminator='kind')]


class Assessment(SourceAttribution):
    assessment_id: NonBlankString
    question_id: NonBlankString
    concept_id: NonBlankString
    outcome: AssessmentOutcome
    feedback: NonBlankString
    confidence: Confidence
    misconceptions: list[NonBlankString] = Field(default_factory=list)
    prerequisite_gaps: list[NonBlankString] = Field(default_factory=list)


class ConceptMastery(Contract):
    concept_id: NonBlankString
    status: MasteryStatus = 'unknown'
    assessment_ids: list[NonBlankString] = Field(default_factory=list)

    @model_validator(mode='after')
    def mastery_has_evidence(self) -> Self:
        if self.status == 'mastered' and not self.assessment_ids:
            raise ValueError('Mastered concepts require assessment evidence.')
        if len(set(self.assessment_ids)) != len(self.assessment_ids):
            raise ValueError('Assessment evidence IDs must be unique.')
        return self


class LearningState(Contract):
    goal: NonBlankString
    phase: LearningPhase = 'diagnose'
    current_concept_id: NonBlankString | None = None
    mastery: list[ConceptMastery] = Field(default_factory=list)

    @model_validator(mode='after')
    def unique_concepts(self) -> Self:
        ids = [record.concept_id for record in self.mastery]
        if len(set(ids)) != len(ids):
            raise ValueError('Mastery records must have unique concept IDs.')
        return self


class _Activity(SourceAttribution):
    activity_id: NonBlankString


class QuestionActivity(_Activity):
    kind: Literal['question'] = 'question'
    question: Question


class ExplanationActivity(_Activity):
    kind: Literal['explanation'] = 'explanation'
    concept_id: NonBlankString
    text: NonBlankString


class HintActivity(_Activity):
    kind: Literal['hint'] = 'hint'
    question_id: NonBlankString
    text: NonBlankString


class FeedbackActivity(_Activity):
    kind: Literal['feedback'] = 'feedback'
    question_id: NonBlankString
    text: NonBlankString


class CompletionActivity(_Activity):
    kind: Literal['completion'] = 'completion'
    text: NonBlankString


LearningActivity = Annotated[
    QuestionActivity | ExplanationActivity | HintActivity | FeedbackActivity | CompletionActivity,
    Field(discriminator='kind'),
]
