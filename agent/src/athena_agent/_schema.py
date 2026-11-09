"""Internal validation primitives shared by agent contracts."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

NonBlankString = Annotated[str, StringConstraints(min_length=1, pattern=r"\S")]


class Contract(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
