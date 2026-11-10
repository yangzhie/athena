"""Scheduling and wording rotation.

FSRS decides *when* an item comes back; `pick_variant` decides *which wording*.
A wrong answer is always rated "again": FSRS then brings the item back within
minutes (its learning steps), so it reappears later in the same session, in a
different wording.
"""

import random
from dataclasses import dataclass
from datetime import UTC, datetime

import fsrs

from .models import (
    CardState,
    Item,
    McqVariant,
    NumericVariant,
    Rating,
    ReviewLogEntry,
    ShortVariant,
    Variant,
)

#: How many recently shown wordings to avoid when there's a choice.
RECENT = 3

_RATINGS: dict[Rating, fsrs.Rating] = {
    "again": fsrs.Rating.Again,
    "hard": fsrs.Rating.Hard,
    "good": fsrs.Rating.Good,
    "easy": fsrs.Rating.Easy,
}


def make_scheduler(*, fuzz: bool = True, desired_retention: float = 0.9) -> fsrs.Scheduler:
    """FSRS with default parameters. Fuzz spreads due dates a little; tests turn it off."""
    return fsrs.Scheduler(desired_retention=desired_retention, enable_fuzzing=fuzz)


def new_card(student_id: str, item_id: str, now: datetime) -> CardState:
    card = fsrs.Card(due=now)
    return CardState(student_id=student_id, item_id=item_id, fsrs=card.to_dict(), due=now)


def is_due(card: CardState, now: datetime) -> bool:
    return card.due <= now


# --- Which wording ----------------------------------------------------------------------


@dataclass(frozen=True)
class Pick:
    """The wording to show, or None when the item needs a live rephrase first."""

    variant: Variant | None
    reason: str


def pick_variant(item: Item, card: CardState, rng: random.Random | None = None) -> Pick:
    """Choose a wording for this review.

    - Never a wording this student got wrong.
    - Only approved wordings (live ones wait for a lecturer, except for the student they were made for).
    - Prefer wordings not shown recently; among those, pick at random.
    - If every remaining wording was shown recently, reuse the least recent one,
      unless the student is retrying after a wrong answer: then ask for a live rephrase.
    """
    rng = rng or random.Random()
    wrong = set(card.wrong_variant_ids)
    mine = set(card.live_variant_ids)
    candidates = [
        v for v in item.variants
        if v.id not in wrong and (v.status == "approved" or (v.id in mine and v.status != "rejected"))
    ]
    if not candidates:
        return Pick(None, "needs a live rephrase: no approved wording left that the student hasn't got wrong")

    recent = card.recent_variant_ids[-RECENT:]
    fresh = [v for v in candidates if v.id not in recent]
    if fresh:
        return Pick(rng.choice(fresh), "fresh wording")

    retrying = bool(card.wrong_variant_ids) and card.recent_variant_ids[-1:] == card.wrong_variant_ids[-1:]
    if retrying:
        return Pick(None, "needs a live rephrase: retrying after a wrong answer and every other wording was just seen")
    least_recent = min(candidates, key=lambda v: recent.index(v.id))
    return Pick(least_recent, "least recently seen wording")


def fallback_variant(item: Item, card: CardState) -> Variant | None:
    """When a live rephrase isn't possible: the least recently seen approved wording the
    student hasn't got wrong. None if every one was answered wrong (never repeat those)."""
    wrong = set(card.wrong_variant_ids)
    candidates = [v for v in item.variants if v.id not in wrong and v.status == "approved"]
    if not candidates:
        return None
    recent = card.recent_variant_ids
    return min(candidates, key=lambda v: recent.index(v.id) if v.id in recent else -1)


def base_for_rephrase(item: Item, card: CardState) -> Variant:
    """Which approved wording to rewrite: the one the student most recently got wrong, else any."""
    approved = [v for v in item.variants if v.status == "approved"] or list(item.variants)
    for vid in reversed(card.wrong_variant_ids):
        v = item.variant(vid)
        if v is not None and v.status == "approved":
            return v
    return approved[0]


# --- Grading ------------------------------------------------------------------------------


def grade(variant: Variant, answer: int | float | str) -> bool | None:
    """True/False for multiple choice and numeric; None for short answers (self-assessed for now)."""
    if isinstance(variant, McqVariant):
        return isinstance(answer, int) and not isinstance(answer, bool) and answer == variant.answer_index
    if isinstance(variant, NumericVariant):
        try:
            value = float(answer)
        except (TypeError, ValueError):
            return False
        return abs(value - variant.answer) <= variant.tolerance + 1e-9
    if isinstance(variant, ShortVariant):
        return None
    raise TypeError(f"unknown variant kind: {variant!r}")


# --- Recording a review ---------------------------------------------------------------------


class ReviewError(ValueError):
    pass


def review(
    card: CardState,
    item: Item,
    variant_id: str,
    *,
    correct: bool | None,
    rating: Rating,
    now: datetime | None = None,
    scheduler: fsrs.Scheduler | None = None,
    duration_ms: int | None = None,
) -> tuple[CardState, ReviewLogEntry]:
    """Apply one answer: update FSRS, the wording history, and return the log entry."""
    now = now or datetime.now(UTC)
    scheduler = scheduler or make_scheduler()
    if card.item_id != item.id:
        raise ReviewError("card and item don't match")
    if item.variant(variant_id) is None:
        raise ReviewError(f"item {item.id} has no variant {variant_id!r}")
    if correct is False and rating != "again":
        raise ReviewError("a wrong answer must be rated 'again'")
    if correct is True and rating == "again":
        raise ReviewError("a right answer can't be rated 'again'")

    updated, _ = scheduler.review_card(fsrs.Card.from_dict(card.fsrs), _RATINGS[rating], now)
    failed = rating == "again"
    wrong = card.wrong_variant_ids + ([variant_id] if failed and variant_id not in card.wrong_variant_ids else [])

    new_state = card.model_copy(
        update={
            "fsrs": updated.to_dict(),
            "due": updated.due,
            "recent_variant_ids": (card.recent_variant_ids + [variant_id])[-RECENT:],
            "wrong_variant_ids": wrong,
        }
    )
    log = ReviewLogEntry(
        student_id=card.student_id,
        item_id=item.id,
        variant_id=variant_id,
        correct=correct,
        rating=rating,
        reviewed_at=now,
        duration_ms=duration_ms,
    )
    return new_state, log
