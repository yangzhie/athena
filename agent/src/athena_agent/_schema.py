"""Internal validation primitives shared by agent contracts."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, PrivateAttr, StringConstraints

NonBlankString = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]


class Contract(BaseModel):
    # Internal generation provenance; excluded from schemas and serialized model output.
    _source_references: list = PrivateAttr(default_factory=list)

    model_config = ConfigDict(strict=True, extra="forbid")
