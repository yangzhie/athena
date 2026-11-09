"""External retrieval contracts; ingestion, indexing, and media stay outside the agent."""

from collections import deque
from copy import deepcopy
from typing import Annotated, Literal, Protocol, Self, Sequence

from pydantic import Field, ValidationError, model_validator

from ._schema import Contract, NonBlankString


class RetrievalRequest(Contract):
    query: NonBlankString
    source_ids: Annotated[list[NonBlankString], Field(min_length=1)] | None = None
    max_results: Annotated[int, Field(ge=1)] = 5


class DocumentPassage(Contract):
    kind: Literal['document'] = 'document'
    source_id: NonBlankString
    passage_id: NonBlankString
    title: NonBlankString
    text: NonBlankString
    source_uri: NonBlankString | None = None
    page: Annotated[int, Field(ge=1)] | None = None
    section: NonBlankString | None = None


class VideoSegment(Contract):
    kind: Literal['video'] = 'video'
    source_id: NonBlankString
    segment_id: NonBlankString
    title: NonBlankString
    transcript: NonBlankString
    source_uri: NonBlankString | None = None
    start_seconds: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    end_seconds: Annotated[float, Field(gt=0, allow_inf_nan=False)]

    @model_validator(mode='after')
    def valid_time_range(self) -> Self:
        if self.end_seconds <= self.start_seconds:
            raise ValueError('Video segment end must be after its start.')
        return self


RetrievalItem = Annotated[DocumentPassage | VideoSegment, Field(discriminator='kind')]


class RetrievalResult(Contract):
    items: list[RetrievalItem] = Field(default_factory=list)

    @model_validator(mode='after')
    def unique_references(self) -> Self:
        keys = [
            (item.kind, item.source_id,
             item.passage_id if isinstance(item, DocumentPassage) else item.segment_id)
            for item in self.items
        ]
        if len(set(keys)) != len(keys):
            raise ValueError('Retrieved references must be unique within a result.')
        return self


class RetrievalError(Exception):
    """Safe retrieval dependency failure, distinct from a successful empty result."""

    def __init__(self, message: str = 'The retrieval service is unavailable.', *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class Retriever(Protocol):
    async def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        """Return relevant, authorized results respecting source scope and limit.

        Identity/access controls belong to the host service; source IDs alone do
        not authorize access. Retrieved text is data, never agent instructions.
        """
        ...


class MockRetriever:
    """Script results or failures without searching, networking, or fabricating citations."""

    def __init__(self, results: Sequence[RetrievalResult | dict | RetrievalError]):
        self._results = deque(
            result if isinstance(result, RetrievalError) else deepcopy(result)
            for result in results
        )
        self.calls: list[RetrievalRequest] = []

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        self.calls.append(request.model_copy(deep=True))
        if not self._results:
            raise RetrievalError('No scripted retrieval results remain.')
        result = self._results.popleft()
        if isinstance(result, RetrievalError):
            raise result
        try:
            if isinstance(result, RetrievalResult):
                result = result.model_dump(mode='python')
            validated = RetrievalResult.model_validate(result)
        except ValidationError:
            raise RetrievalError('The retrieval service returned invalid results.') from None
        scoped = [
            item for item in validated.items
            if request.source_ids is None or item.source_id in request.source_ids
        ]
        return RetrievalResult(items=scoped[:request.max_results])
