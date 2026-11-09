"""Client request bodies deliberately exclude trusted learner identity."""

from typing import Annotated

from pydantic import Field

from ._schema import Contract, NonBlankString
from .learning import Difficulty
from .activities import ClientCapabilities
from .retrieval import RetrievalResult


class StartSession(Contract):
    model_config = {'json_schema_extra': {'examples': [{
        'session_id': 'session-1', 'goal': 'Bubble Sort', 'difficulty': 'beginner',
        'capabilities': {'formats': ['text', 'diagram']},
    }]}}
    session_id: NonBlankString
    goal: NonBlankString
    difficulty: Difficulty = 'beginner'
    materials: RetrievalResult | None = None
    capabilities: ClientCapabilities | None = None


class MessageSubmission(Contract):
    model_config = {'json_schema_extra': {'examples': [{'text': 'Explain the adjacent comparison again.'}]}}
    text: NonBlankString


class ContinueSubmission(Contract):
    model_config = {'json_schema_extra': {'examples': [{'activity_id': 'activity-1'}]}}
    activity_id: NonBlankString


class MaterialSubmission(Contract):
    model_config = {'json_schema_extra': {'examples': [{'result': {'items': [{
        'kind': 'document', 'source_id': 'sorting-notes', 'passage_id': 'adjacent-pairs',
        'title': 'Sorting notes', 'text': 'Bubble Sort compares adjacent values.', 'page': 2,
    }]}}]}}
    result: RetrievalResult
    source_ids: Annotated[list[NonBlankString], Field(min_length=1)] | None = None
    max_results: Annotated[int, Field(ge=1)] = 5


class ContentRequest(Contract):
    model_config = {'json_schema_extra': {'examples': [{'concept_id': 'bubble-sort'}]}}
    concept_id: NonBlankString
