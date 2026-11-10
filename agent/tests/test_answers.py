import asyncio

import pytest

from athena_agent.llm import DependencyError, LLMError
from athena_agent.retrieval import RetrievalResult
from .test_conversation_manager import setup

QUESTION = 'What is the difference between regression and classification?'
SOURCES = RetrievalResult.model_validate({'items': [
    {'kind': 'document', 'source_id': 'slides-v1', 'passage_id': 'page-28', 'title': 'Prediction',
     'page': 28, 'text': 'Learning objectives:\nClassification predicts a discrete class label.'},
    {'kind': 'document', 'source_id': 'slides-v1', 'passage_id': 'page-29', 'title': 'Prediction',
     'page': 29, 'text': 'Regression predicts a continuous numerical value.'},
]})
PART = {'text': 'Regression predicts numerical values; classification predicts class labels.', 'origin': 'materials'}
SUPPORTED = {'supported': True, 'evidence': [{'source_index': 0, 'quote_index': 0}, {'source_index': 1, 'quote_index': 0}]}
MISSING = {'supported': False, 'evidence': [], 'problem': 'insufficient_evidence'}


def configured(responses, sources=SOURCES):
    context, store, mock, manager = setup(responses)
    if sources is not None:
        snapshot = store.read(context)
        snapshot.active_topic.knowledge = sources.model_copy(deep=True)
        store._save(context, snapshot)
    return context, store, mock, manager


def test_comparison_uses_multiple_slides_and_preserves_provenance():
    context, store, mock, manager = configured([{'intent': 'continue'}, {'parts': [PART]}, SUPPORTED])
    before = store.read(context)
    reply = asyncio.run(manager.send(context, QUESTION))
    assert reply.text == PART['text'] and reply.knowledge_origin == 'materials'
    assert [r.page for r in reply.sources] == [28, 29]
    assert reply.sources[0].quote == SOURCES.items[0].text
    assert store.read(context).active_topic.learning_state == before.active_topic.learning_state
    assert len(mock.calls) == 3


def test_partial_coverage_has_server_rendered_labels_and_only_verified_sources():
    general = {'text': 'For example, predicting tomorrow’s temperature is regression.', 'origin': 'general'}
    context, _, _, manager = configured([{'intent': 'continue'}, {'parts': [PART, general]}, SUPPORTED])
    reply = asyncio.run(manager.send(context, QUESTION))
    assert '**From your material:** ' + PART['text'] in reply.text
    assert '**General-knowledge addition:** ' + general['text'] in reply.text
    assert reply.knowledge_origin == 'supplement' and len(reply.sources) == 2


def test_supported_answer_cannot_be_mislabelled_as_general():
    context, _, _, manager = configured([{'intent': 'continue'}, {'parts': [{**PART, 'origin': 'general'}]}, SUPPORTED])
    reply = asyncio.run(manager.send(context, QUESTION))
    assert reply.knowledge_origin == 'materials' and reply.sources


def test_missing_coverage_returns_general_answer_without_false_citations():
    general = {'parts': [{'text': 'A numerical prediction is regression; a class label is classification.', 'origin': 'general'}]}
    context, store, mock, manager = configured([{'intent': 'continue'}, general, MISSING, general, MISSING])
    before = store.read(context)
    reply = asyncio.run(manager.send(context, QUESTION))
    assert reply.knowledge_origin == 'general' and reply.sources == []
    assert reply.text == general['parts'][0]['text'] and len(mock.calls) == 5
    assert store.read(context).active_topic.knowledge == before.active_topic.knowledge


def test_unsupported_addition_is_repaired_once_before_losing_grounding():
    context, _, mock, manager = configured([
        {'intent': 'continue'}, {'parts': [PART]}, MISSING, {'parts': [PART]}, SUPPORTED,
    ])
    reply = asyncio.run(manager.send(context, QUESTION))
    assert reply.knowledge_origin == 'materials' and len(mock.calls) == 5


def test_failed_repairs_fall_back_without_clearing_selected_material():
    context, store, mock, manager = configured([
        {'intent': 'continue'}, {'parts': [PART]}, MISSING, {'parts': [PART]}, MISSING,
        {'text': 'Regression predicts a number; classification predicts a label.'},
    ])
    reply = asyncio.run(manager.send(context, QUESTION))
    assert reply.knowledge_origin == 'general' and reply.sources == []
    assert store.read(context).active_topic.knowledge == SOURCES
    assert len(mock.calls) == 6
    assert 'selected_materials' not in mock.calls[-1].messages[1].content


def test_no_retrieved_sources_still_answers_with_general_origin():
    context, _, mock, manager = configured([{'intent': 'continue'}, {'text': PART['text']}], sources=None)
    reply = asyncio.run(manager.send(context, QUESTION))
    assert reply.knowledge_origin == 'general' and reply.sources == []
    assert len(mock.calls) == 2


@pytest.mark.parametrize('check', [
    {**SUPPORTED, 'followed_source_instructions': True},
    {**SUPPORTED, 'contradicts_sources': True},
    {'supported': False, 'problem': 'conflicting_sources', 'evidence': SUPPORTED['evidence']},
    {'supported': True, 'evidence': [{'source_index': 0, 'quote_index': 999}]},
    DependencyError('Provider unavailable'),
])
def test_errors_and_conflicts_never_trigger_general_fallback(check):
    context, store, mock, manager = configured([{'intent': 'continue'}, {'parts': [PART]}, check])
    before = store.read(context)
    with pytest.raises(LLMError):
        asyncio.run(manager.send(context, QUESTION))
    assert store.read(context) == before and len(mock.calls) == 3


def test_question_material_survives_an_explicit_topic_switch():
    context, store, _, manager = configured([
        {'intent': 'topic_change', 'new_goal': 'Regression and classification'}, {'parts': [PART]}, SUPPORTED,
    ])
    reply = asyncio.run(manager.send(context, 'Switch to regression and classification.'))
    assert reply.knowledge_origin == 'materials'
    assert store.read(context).active_topic.knowledge == SOURCES
