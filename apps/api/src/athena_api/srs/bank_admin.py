"""Lecturer side of SRS: review the question bank.

Lecturers see every item and wording with answers, approve or reject wordings
(generated and live ones arrive pending), and edit them. Nothing here touches
or returns student data: live wordings carry no student id.
"""

from dataclasses import dataclass

from pydantic import TypeAdapter, ValidationError

from .models import Bank, Item, Variant
from .store import SrsStore

_variant = TypeAdapter(Variant)

#: Fields a lecturer may edit, per kind (ids, origin and status are managed separately).
EDITABLE = {
    "mcq": {"stem", "explanation", "options", "answer_index"},
    "numeric": {"stem", "explanation", "answer", "tolerance"},
    "short": {"stem", "explanation", "model_answer", "rubric"},
}


class NotFound(LookupError):
    pass


class Invalid(ValueError):
    pass


@dataclass
class BankAdmin:
    store: SrsStore

    def bank(self, offering_id: str) -> Bank:
        bank = self.store.get_bank(offering_id)
        if bank is None:
            raise NotFound("this unit has no question bank yet")
        return bank

    def _replace(self, bank: Bank, item_id: str, variant_id: str, fn) -> Variant:
        item = next((i for i in bank.items if i.id == item_id), None)
        if item is None or item.variant(variant_id) is None:
            raise NotFound("no such question wording")
        new_variant = fn(item.variant(variant_id))
        new_item = item.model_copy(update={"variants": [new_variant if v.id == variant_id else v for v in item.variants]})
        Item.model_validate(new_item.model_dump())
        self.store.put_bank(bank.model_copy(update={"items": [new_item if i.id == item_id else i for i in bank.items]}))
        return new_variant

    def set_status(self, offering_id: str, item_id: str, variant_id: str, status: str) -> Variant:
        if status not in ("approved", "rejected", "pending"):
            raise Invalid("status must be approved, rejected or pending")
        return self._replace(self.bank(offering_id), item_id, variant_id, lambda v: v.model_copy(update={"status": status}))

    def edit(self, offering_id: str, item_id: str, variant_id: str, changes: dict) -> Variant:
        def apply(v: Variant) -> Variant:
            unknown = set(changes) - EDITABLE[v.kind]
            if unknown:
                raise Invalid(f"can't edit {', '.join(sorted(unknown))} on a {v.kind} question")
            try:
                return _variant.validate_python({**v.model_dump(), **changes})
            except ValidationError as e:
                raise Invalid(e.errors()[0]["msg"]) from None

        return self._replace(self.bank(offering_id), item_id, variant_id, apply)

    def approve_pending(self, offering_id: str, item_ids: list[str] | None = None) -> int:
        """Approve every pending wording (optionally only in some items). Returns how many."""
        bank = self.bank(offering_id)
        count = 0
        items = []
        for item in bank.items:
            if item_ids is None or item.id in item_ids:
                variants = []
                for v in item.variants:
                    if v.status == "pending":
                        v = v.model_copy(update={"status": "approved"})
                        count += 1
                    variants.append(v)
                item = item.model_copy(update={"variants": variants})
            items.append(item)
        self.store.put_bank(bank.model_copy(update={"items": items}))
        return count
