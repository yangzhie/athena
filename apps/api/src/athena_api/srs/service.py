"""SRS use cases: what to review next, answering, rating, and a summary.

Pure orchestration over a store, the scheduler and an injectable clock, so the
HTTP layer stays thin and everything is testable with fixed times.
"""

import random
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

import fsrs

from .models import (
    Bank,
    CardState,
    Item,
    McqVariant,
    NumericVariant,
    Rating,
    ShortVariant,
    Variant,
)
from .rephrase import Rephraser, RephraseError, rephrase
from .scheduler import base_for_rephrase, fallback_variant, grade, make_scheduler, new_card, pick_variant, review
from .store import Attempt, SrsStore, CommandConflict

#: New items introduced per student, per unit, per day.
NEW_PER_DAY = 10


class NotFound(LookupError):
    pass


class Conflict(ValueError):
    pass


def _start_of_day(now: datetime) -> datetime:
    return now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def question_view(variant: Variant) -> dict:
    """What the student sees before answering. Never includes the answer."""
    base = {"variant_id": variant.id, "kind": variant.kind, "stem": variant.stem}
    if isinstance(variant, McqVariant):
        base["options"] = list(variant.options)
    return base


def feedback_view(variant: Variant, item: Item) -> dict:
    """What the student sees after answering."""
    out: dict = {"explanation": variant.explanation, "clip_ids": list(item.clip_ids)}
    if isinstance(variant, McqVariant):
        out["correct_option"] = variant.answer_index
    elif isinstance(variant, NumericVariant):
        out["correct_value"] = variant.answer
    elif isinstance(variant, ShortVariant):
        out["model_answer"] = variant.model_answer
        out["rubric"] = list(variant.rubric)
    return out


@dataclass
class SrsService:
    store: SrsStore
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    scheduler: fsrs.Scheduler = field(default_factory=make_scheduler)
    rng: random.Random = field(default_factory=random.Random)
    new_per_day: int = NEW_PER_DAY
    #: Writes a new wording when a student runs out of fresh ones. None disables it.
    rephraser: Rephraser | None = None

    private_items: Callable[[str, str], list[Item]] | None = None
    private_item_writer: Callable[[str, Item], None] | None = None
    practice_sink: Callable | None = None

    def _bank(self, offering_id: str, student_id: str | None = None) -> Bank:
        bank = self.store.get_bank(offering_id)
        private = self.private_items(student_id, offering_id) if self.private_items and student_id else []
        if self.private_items is not None:
            return Bank(offering_id=offering_id, items=[*(bank.items if bank else []), *private])
        if bank is None:
            raise NotFound("this unit has no question bank yet")
        return bank

    def _item(self, bank: Bank, item_id: str) -> Item:
        item = next((i for i in bank.items if i.id == item_id), None)
        if item is None:
            raise NotFound("no such question")
        return item

    # --- what's next --------------------------------------------------------------------

    def next(self, student_id: str, offering_id: str) -> dict:
        now = self.clock()
        bank = self._bank(offering_id, student_id)
        items = {i.id: i for i in bank.items}
        cards = {c.item_id: c for c in self.store.list_cards(student_id, offering_id) if c.item_id in items}

        due = sorted((c for c in cards.values() if c.due <= now), key=lambda c: c.due)
        new_left = max(0, self.new_per_day - self.store.count_cards_created_since(student_id, offering_id, _start_of_day(now)))
        unseen = sorted((i for i in bank.items if i.id not in cards), key=lambda i: (i.difficulty, i.id))[:new_left]

        candidates: list[tuple[Item, CardState]] = [(items[c.item_id], c) for c in due]
        candidates += [(i, new_card(student_id, i.id, now)) for i in unseen]
        for item, card in candidates:
            variant = pick_variant(item, card, self.rng).variant or self._new_wording(bank, item, card)
            if variant is not None:
                return {
                    "done": False,
                    "item_id": item.id,
                    "topic_id": item.topic_id,
                    "is_new": item.id not in cards,
                    "question": question_view(variant),
                    "remaining": {"due": len(due), "new": len(unseen)},
                }

        upcoming = [c.due for c in cards.values() if c.due > now]
        return {"done": True, "next_due_at": min(upcoming) if upcoming else None}

    def _new_wording(self, bank: Bank, item: Item, card: CardState) -> Variant | None:
        """Live rephrase (saved as pending), else a fallback wording, else None (item waits)."""
        if self.rephraser is not None:
            try:
                variant = rephrase(item, base_for_rephrase(item, card), self.rephraser, self.rng)
            except RephraseError:
                variant = None
            if variant is not None:
                updated = item.model_copy(update={"variants": [*item.variants, variant]})
                if item.id.startswith('private:'):
                    if self.private_item_writer is None:
                        return fallback_variant(item, card)
                    self.private_item_writer(card.student_id, updated)
                else:
                    # Never persist the merged learner-only bank into the public bank.
                    public = self.store.get_bank(bank.offering_id)
                    if public is not None:
                        self.store.put_bank(public.model_copy(update={"items": [updated if i.id == item.id else i for i in public.items]}))
                # Remember it on the student's card, so a page refresh reuses it instead of writing another.
                if self.store.get_card(card.student_id, item.id) is not None:
                    mine = card.model_copy(update={"live_variant_ids": [*card.live_variant_ids, variant.id]})
                    self.store.put_card(mine, bank.offering_id, created_at=self.clock())
                return variant
        return fallback_variant(item, card)

    # --- answering ------------------------------------------------------------------------

    def answer(self, student_id: str, offering_id: str, item_id: str, variant_id: str, answer: int | float | str | None, operation_id: str | None = None) -> dict:
        bank = self._bank(offering_id, student_id)  # Private projection reads happen before the store transaction.
        try:
            result = self.store.command(student_id, offering_id, 'answer:' + operation_id if operation_id else None,
                                        {'item_id': item_id, 'variant_id': variant_id, 'answer': answer},
                                        lambda: self._answer(student_id, offering_id, item_id, variant_id, answer, bank))
        except CommandConflict as error:
            raise Conflict(str(error)) from None
        self._practice_projection(student_id, offering_id, result['attempt_id'])
        return result

    def _answer(self, student_id, offering_id, item_id, variant_id, answer, bank):
        now = self.clock()
        item = self._item(bank, item_id)
        variant = item.variant(variant_id)
        if variant is None:
            raise NotFound("no such wording")
        if answer is None and not isinstance(variant, ShortVariant):
            raise Conflict("an answer is required")

        correct = grade(variant, "" if answer is None else answer)
        attempt = Attempt(
            id=uuid.uuid4().hex, student_id=student_id, offering_id=offering_id,
            item_id=item.id, variant_id=variant.id, correct=correct, created_at=now,
        )
        self.store.add_attempt(attempt)

        out = {"attempt_id": attempt.id, "correct": correct, "feedback": feedback_view(variant, item)}
        if correct is False:
            # Wrong answers are always "again": record now; the item returns soon, reworded.
            out["next_due_at"] = self._record(student_id, offering_id, item, attempt, "again")
            out["needs_rating"] = False
        else:
            out["needs_rating"] = True
            out["rating_options"] = ["hard", "good", "easy"] if correct else ["again", "hard", "good", "easy"]
        return out

    def rate(self, student_id: str, offering_id: str, attempt_id: str, rating: Rating, operation_id: str | None = None) -> dict:
        bank = self._bank(offering_id, student_id)
        try:
            result = self.store.command(student_id, offering_id, 'rating:' + operation_id if operation_id else None,
                                        {'attempt_id': attempt_id, 'rating': rating},
                                        lambda: self._rate(student_id, offering_id, attempt_id, rating, bank))
        except CommandConflict as error:
            raise Conflict(str(error)) from None
        self._practice_projection(student_id, offering_id, attempt_id)
        return result

    def recover(self, student_id, offering_id, operation_id):
        saved = self.store.get_command(student_id, offering_id, operation_id)
        if saved is None:
            raise NotFound('This Practice operation did not commit.')
        payload, result = saved
        attempt_id = result.get('attempt_id') or payload.get('attempt_id')
        if attempt_id:
            self._practice_projection(student_id, offering_id, attempt_id)
        return result

    def pending(self, student_id, offering_id):
        attempt = self.store.pending_attempt(student_id, offering_id)
        if attempt is None:
            return None
        item = self._item(self._bank(offering_id, student_id), attempt.item_id)
        variant = item.variant(attempt.variant_id)
        if variant is None:
            raise NotFound('The saved question wording is unavailable.')
        summary = self.summary(student_id, offering_id)
        return dict(done=False, item_id=item.id, topic_id=item.topic_id,
                    is_new=self.store.get_card(student_id, item.id) is None, question=question_view(variant),
                    remaining={'due': summary['due_now'], 'new': summary['new_available']},
                    restored_attempt=dict(attempt_id=attempt.id, correct=attempt.correct, feedback=feedback_view(variant, item),
                                          needs_rating=True, rating_options=['hard', 'good', 'easy'] if attempt.correct else ['again', 'hard', 'good', 'easy']))

    def _practice_projection(self, student_id, offering_id, attempt_id):
        if self.practice_sink:
            attempt = self.store.get_attempt(student_id, attempt_id)
            if attempt and attempt.rated:
                self.practice_sink(student_id, offering_id, attempt_id, None, attempt.correct)

    def _rate(self, student_id, offering_id, attempt_id, rating, bank):
        attempt = self.store.get_attempt(student_id, attempt_id)
        if attempt is None or attempt.offering_id != offering_id:
            raise NotFound("no such attempt")
        if attempt.rated:
            raise Conflict("this attempt is already rated")
        item = self._item(bank, attempt.item_id)
        return {"next_due_at": self._record(student_id, offering_id, item, attempt, rating)}

    def _record(self, student_id: str, offering_id: str, item: Item, attempt: Attempt, rating: Rating) -> datetime:
        now = self.clock()
        card = self.store.get_card(student_id, item.id)
        card = card or new_card(student_id, item.id, attempt.created_at)
        updated, log = review(
            card, item, attempt.variant_id, correct=attempt.correct, rating=rating, now=now,
            scheduler=self.scheduler,
            duration_ms=int((now - attempt.created_at).total_seconds() * 1000),
        )
        self.store.put_card(updated, offering_id, created_at=now)  # only stored when the card is new
        self.store.add_log(log, offering_id)
        self.store.mark_attempt_rated(student_id, attempt.id)
        return updated.due

    # --- summary ----------------------------------------------------------------------------

    def summary(self, student_id: str, offering_id: str) -> dict:
        now = self.clock()
        bank = self._bank(offering_id, student_id)
        cards = self.store.list_cards(student_id, offering_id)
        known = {c.item_id for c in cards}
        today = _start_of_day(now)
        new_left = max(0, self.new_per_day - self.store.count_cards_created_since(student_id, offering_id, today))
        upcoming = [c.due for c in cards if c.due > now]
        return {
            "total_items": len(bank.items),
            "due_now": sum(1 for c in cards if c.due <= now),
            "new_available": min(new_left, sum(1 for i in bank.items if i.id not in known)),
            "reviewed_today": self.store.count_logs_since(student_id, offering_id, today),
            "next_due_at": min(upcoming) if upcoming else None,
        }

