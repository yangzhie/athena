"""SRS data: question bank items (one idea, many wordings), per-student cards, review logs.

Scheduling is per *item* (an idea). Each time an item comes back the student
gets one of its variants: a different wording, framing or input data, never
the exact one they last got wrong.
"""

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonBlank = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]


class Model(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


# --- Variants: one wording of an item -------------------------------------------------


class _Variant(Model):
    id: NonBlank
    stem: NonBlank
    #: Shown after answering, right or wrong.
    explanation: NonBlank
    #: bank = written or generated in advance; live = rephrased by the LLM during a review.
    origin: Literal["bank", "live"] = "bank"
    #: Live variants start pending until a lecturer checks them.
    status: Literal["approved", "pending"] = "approved"


class McqVariant(_Variant):
    kind: Literal["mcq"] = "mcq"
    options: Annotated[list[NonBlank], Field(min_length=2, max_length=6)]
    answer_index: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def _valid(self) -> Self:
        if self.answer_index >= len(self.options):
            raise ValueError("answer_index is not one of the options")
        if len({o.strip().lower() for o in self.options}) != len(self.options):
            raise ValueError("options must all be different")
        return self


class NumericVariant(_Variant):
    kind: Literal["numeric"] = "numeric"
    answer: float
    #: Accepted absolute difference from `answer`.
    tolerance: Annotated[float, Field(ge=0)] = 0.0


class ShortVariant(_Variant):
    kind: Literal["short"] = "short"
    model_answer: NonBlank
    #: Points a good answer must make; used for grading.
    rubric: Annotated[list[NonBlank], Field(min_length=1)]


Variant = Annotated[McqVariant | NumericVariant | ShortVariant, Field(discriminator="kind")]


# --- Items and banks --------------------------------------------------------------------


class Item(Model):
    """One idea to remember, with several wordings of the question."""

    id: NonBlank
    offering_id: NonBlank
    topic_id: NonBlank
    #: The idea in one sentence, e.g. "Insertion sort is O(n²) in the worst case because each element may shift past all earlier ones".
    concept: NonBlank
    difficulty: Annotated[int, Field(ge=1, le=5)]
    bloom: Literal["recall", "apply", "analyse"]
    variants: Annotated[list[Variant], Field(min_length=1)]
    #: Lecture clips that teach this idea, offered after a wrong answer.
    clip_ids: list[NonBlank] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_variants(self) -> Self:
        ids = [v.id for v in self.variants]
        if len(set(ids)) != len(ids):
            raise ValueError("variant ids must be unique within an item")
        return self

    def variant(self, variant_id: str) -> Variant | None:
        return next((v for v in self.variants if v.id == variant_id), None)


class Bank(Model):
    """All SRS items for one offering."""

    offering_id: NonBlank
    items: list[Item]

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        ids = [i.id for i in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError("item ids must be unique within a bank")
        if any(i.offering_id != self.offering_id for i in self.items):
            raise ValueError("every item must belong to the bank's offering")
        return self


# --- Per-student state ---------------------------------------------------------------------


class CardState(Model):
    """One student's schedule for one item. Private to that student."""

    student_id: NonBlank
    item_id: NonBlank
    #: fsrs.Card.to_dict(); the FSRS library owns this shape.
    fsrs: dict
    due: datetime
    #: Variant ids shown most recently, oldest first. Used to rotate wording.
    recent_variant_ids: list[NonBlank] = Field(default_factory=list)
    #: Wordings this student answered wrong. Never shown to them again: a retry
    #: always uses a different wording (or a live rephrase when none are left).
    wrong_variant_ids: list[NonBlank] = Field(default_factory=list)


Rating = Literal["again", "hard", "good", "easy"]


class ReviewLogEntry(Model):
    """One answer. Private to the student; only derived signals ever leave the environment."""

    student_id: NonBlank
    item_id: NonBlank
    variant_id: NonBlank
    #: None for short answers the student self-assessed.
    correct: bool | None
    rating: Rating
    reviewed_at: datetime
    duration_ms: Annotated[int, Field(ge=0)] | None = None
