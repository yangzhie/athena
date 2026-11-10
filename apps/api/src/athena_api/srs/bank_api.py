"""Lecturer routes for reviewing a unit's SRS question bank."""

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from ..auth import LecturerResolver, lecturer_dependency
from .bank_admin import BankAdmin, Invalid, NotFound
from .models import Bank, Variant


class StatusBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["approved", "rejected", "pending"]


class ApproveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    #: Only these items; all items when omitted.
    item_ids: list[str] | None = None


def bank_router(admin: BankAdmin, resolve_lecturer: LecturerResolver) -> APIRouter:
    router = APIRouter(prefix="/units/{offering_id}/srs/bank", tags=["srs-lecturer"])
    Lecturer = lecturer_dependency(resolve_lecturer)

    def run(fn, *args):
        try:
            return fn(*args)
        except NotFound as e:
            raise HTTPException(404, str(e)) from None
        except Invalid as e:
            raise HTTPException(422, str(e)) from None

    @router.get("", response_model=Bank)
    def get_bank(offering_id: str, _: Lecturer):
        return run(admin.bank, offering_id)

    @router.post("/items/{item_id}/variants/{variant_id}/status", response_model=Variant)
    def set_status(offering_id: str, item_id: str, variant_id: str, body: StatusBody, _: Lecturer):
        return run(admin.set_status, offering_id, item_id, variant_id, body.status)

    @router.patch("/items/{item_id}/variants/{variant_id}", response_model=Variant)
    def edit(offering_id: str, item_id: str, variant_id: str, changes: dict, _: Lecturer):
        return run(admin.edit, offering_id, item_id, variant_id, changes)

    @router.post("/approve-pending")
    def approve_pending(offering_id: str, body: ApproveBody, _: Lecturer):
        return {"approved": run(admin.approve_pending, offering_id, body.item_ids)}

    return router
