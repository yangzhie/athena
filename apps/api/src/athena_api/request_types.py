"""Host HTTP contracts shared by independently developed feature routers."""
from typing import Annotated
from fastapi import Header

OperationId = Annotated[str | None, Header(alias='Idempotency-Key', min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_-]+$')]
