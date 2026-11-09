"""Planning data contracts, independent of session storage and providers."""

from typing import Literal

from ._schema import Contract, NonBlankString


class TopicScope(Contract):
    scope: Literal['narrow', 'broad']
    rationale: NonBlankString
