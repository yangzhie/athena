"""Client request bodies deliberately exclude trusted learner identity."""

from typing import Annotated

from pydantic import Field

from ._schema import Contract, NonBlankString
from .learning import Difficulty
from .activities import ClientCapabilities
from .retrieval import RetrievalResult


class StartSession(Contract):
    session_id: NonBlankString
    goal: NonBlankString
    difficulty: Difficulty = 'beginner'
    materials: RetrievalResult | None = None
    capabilities: ClientCapabilities | None = None


class MessageSubmission(Contract):
    text: NonBlankString


class ContinueSubmission(Contract):
    activity_id: NonBlankString


class MaterialSubmission(Contract):
    result: RetrievalResult
    source_ids: Annotated[list[NonBlankString], Field(min_length=1)] | None = None
    max_results: Annotated[int, Field(ge=1)] = 5


class ContentRequest(Contract):
    concept_id: NonBlankString
