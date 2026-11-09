"""Internal assessment records and model-output contracts."""

from typing import Annotated, Self

from pydantic import Field, model_validator

from ._schema import Contract, NonBlankString
from .learning import Choice, QuestionWithCriteria


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


class QuestionRecord(Contract):
    """Private bundle; expose only its question through QuestionActivity."""

    activity_id: NonBlankString
    bundle: QuestionWithCriteria
