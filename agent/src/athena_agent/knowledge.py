"""Select external knowledge for a topic; no ingestion or search implementation."""

from pydantic import ValidationError

from .contracts import RequestContext
from .conversation import ConversationError
from .memory import LearningMemoryStore
from .retrieval import Retriever, RetrievalError, RetrievalRequest, RetrievalResult


class KnowledgeService:
    def __init__(self, store: LearningMemoryStore, retriever: Retriever | None = None):
        self.store = store
        self.retriever = retriever

    async def retrieve(self, context: RequestContext, query: str, *, source_ids: list[str] | None = None, max_results: int = 5) -> RetrievalResult:
        request = RetrievalRequest(query=query, source_ids=source_ids, max_results=max_results)
        async with self.store.interaction(context) as session:
            if session.active_topic is None:
                raise ConversationError('Initialize a learning goal before selecting materials.')
            if self.retriever is None:
                raise RetrievalError()
            try:
                result = await self.retriever.retrieve(request.model_copy(deep=True))
                if not isinstance(result, RetrievalResult):
                    raise RetrievalError()
                result = RetrievalResult.model_validate(result.model_dump())
            except (ValidationError, RetrievalError):
                raise RetrievalError() from None
            except Exception:
                raise RetrievalError() from None
            self._validate_scope(result, request)
            session.active_topic.knowledge = result
            self.store._save(context, session)
            return result.model_copy(deep=True)


    @staticmethod
    def _validate_scope(result: RetrievalResult, request: RetrievalRequest) -> None:
        if len(result.items) > request.max_results or any(request.source_ids is not None and item.source_id not in request.source_ids for item in result.items):
            raise RetrievalError('The retrieval service returned results outside the requested scope.')

    async def supply(self, context: RequestContext, result: RetrievalResult, *, source_ids: list[str] | None = None, max_results: int = 5) -> RetrievalResult:
        """Accept host-authorized results using the same selection contract."""
        request = RetrievalRequest(query='Externally supplied learning materials', source_ids=source_ids, max_results=max_results)
        async with self.store.interaction(context) as session:
            if session.active_topic is None:
                raise ConversationError('Initialize a learning goal before selecting materials.')
            try:
                if not isinstance(result, RetrievalResult):
                    raise ConversationError('Supply a validated retrieval result.')
                validated = RetrievalResult.model_validate(result.model_dump())
                self._validate_scope(validated, request)
            except (ValidationError, RetrievalError):
                raise ConversationError('The supplied learning materials are invalid or outside the requested scope.') from None
            session.active_topic.knowledge = validated
            self.store._save(context, session)
            return validated.model_copy(deep=True)
