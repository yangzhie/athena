"""Select external knowledge for a topic; no ingestion or search implementation."""

from pydantic import ValidationError

from .contracts import RequestContext
from .conversation import ConversationError
from .memory import LearningMemoryStore
from .retrieval import Retriever, RetrievalError, RetrievalRequest, RetrievalResult


class KnowledgeService:
    def __init__(self, store: LearningMemoryStore, retriever: Retriever):
        self.store = store
        self.retriever = retriever

    async def retrieve(self, context: RequestContext, query: str, *, source_ids: list[str] | None = None, max_results: int = 5) -> RetrievalResult:
        request = RetrievalRequest(query=query, source_ids=source_ids, max_results=max_results)
        async with self.store.interaction(context) as session:
            if session.active_topic is None:
                raise ConversationError('Initialize a learning goal before selecting materials.')
            try:
                result = await self.retriever.retrieve(request.model_copy(deep=True))
                if not isinstance(result, RetrievalResult):
                    raise RetrievalError()
                result = RetrievalResult.model_validate(result.model_dump())
            except (ValidationError, RetrievalError):
                raise RetrievalError() from None
            except Exception:
                raise RetrievalError() from None
            if len(result.items) > request.max_results or any(request.source_ids is not None and item.source_id not in request.source_ids for item in result.items):
                raise RetrievalError('The retrieval service returned results outside the requested scope.')
            session.active_topic.knowledge = result
            self.store._save(context, session)
            return result.model_copy(deep=True)
