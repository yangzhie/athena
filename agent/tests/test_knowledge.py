import asyncio
import json
from pathlib import Path

import pytest

from athena_agent.contracts import RequestContext
from athena_agent.conversation import ConversationError, InMemoryConversationStore, SessionNotFoundError
from athena_agent.knowledge import KnowledgeService
from athena_agent.retrieval import MockRetriever, RetrievalError, RetrievalResult


def setup():
    context = RequestContext(request_id='r', learner_id='l', session_id='s')
    store = InMemoryConversationStore()
    store.create(context)
    store.initialize_goal(context, 'Bubble Sort')
    return context, store


def material():
    return RetrievalResult.model_validate(json.loads((Path(__file__).parent / 'fixtures/retrieval.json').read_text()))


def test_retrieve_requests_scoped_documents_and_video_and_saves_copy():
    context, store = setup()
    result = material()
    mock = MockRetriever([result])
    service = KnowledgeService(store, mock)
    retrieved = asyncio.run(service.retrieve(context, 'Bubble Sort', source_ids=[item.source_id for item in result.items]))
    assert {item.kind for item in retrieved.items} == {'document', 'video'}
    assert mock.calls[0].query == 'Bubble Sort'
    assert store.read(context).active_topic.knowledge == result
    retrieved.items.clear()
    assert store.read(context).active_topic.knowledge == result


def test_failure_foreign_and_cancellation_do_not_change_selection():
    context, store = setup()
    service = KnowledgeService(store, MockRetriever([RetrievalError()]))
    before = store.read(context)
    with pytest.raises(SessionNotFoundError):
        asyncio.run(service.retrieve(context.model_copy(update={'learner_id': 'other'}), 'Topic'))
    with pytest.raises(RetrievalError):
        asyncio.run(service.retrieve(context, 'Topic'))
    class Cancelled:
        async def retrieve(self, request):
            raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(KnowledgeService(store, Cancelled()).retrieve(context, 'Topic'))
    assert store.read(context) == before


def test_out_of_scope_results_rejected_and_stale_selection_does_not_overwrite():
    context, store = setup()
    class Provider:
        async def retrieve(self, request):
            return material()
    before = store.read(context)
    with pytest.raises(RetrievalError):
        asyncio.run(KnowledgeService(store, Provider()).retrieve(context, 'Topic', source_ids=['not-authorized']))
    assert store.read(context) == before
    class Stale:
        async def retrieve(self, request):
            store.update_focus(context, 'Newer focus')
            return material()
    with pytest.raises(ConversationError, match='session changed'):
        asyncio.run(KnowledgeService(store, Stale()).retrieve(context, 'Topic'))
    assert store.read(context).active_topic.knowledge is None


def test_external_results_share_selection_contract_without_retriever():
    context, store = setup()
    service = KnowledgeService(store)
    supplied = material()
    accepted = asyncio.run(service.supply(context, supplied))
    assert accepted == store.read(context).active_topic.knowledge == supplied
    supplied.items.clear()
    assert store.read(context).active_topic.knowledge == accepted
    before = store.read(context)
    with pytest.raises(ConversationError, match='outside'):
        asyncio.run(service.supply(context, accepted, source_ids=['not-selected']))
    with pytest.raises(SessionNotFoundError):
        asyncio.run(service.supply(context.model_copy(update={'learner_id': 'other'}), accepted))
    with pytest.raises(RetrievalError):
        asyncio.run(service.retrieve(context, 'Topic'))
    assert store.read(context) == before


def test_empty_external_result_is_explicit_selection():
    context, store = setup()
    asyncio.run(KnowledgeService(store).supply(context, RetrievalResult()))
    assert store.read(context).active_topic.knowledge == RetrievalResult()
