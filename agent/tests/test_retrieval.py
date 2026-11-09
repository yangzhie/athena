import asyncio
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from athena_agent.retrieval import (
    DocumentPassage, MockRetriever, RetrievalError, RetrievalRequest,
    RetrievalResult, VideoSegment,
)


@pytest.fixture
def results():
    return RetrievalResult.model_validate_json(
        (Path(__file__).parent / 'fixtures' / 'retrieval.json').read_text(),
    )


def retrieve(mock, **kwargs):
    return asyncio.run(mock.retrieve(RetrievalRequest(query='Bubble Sort', **kwargs)))


def test_reference_round_trip_and_schema(results):
    assert RetrievalResult.model_validate_json(results.model_dump_json()) == results
    assert results.items[0].page == 3
    assert results.items[1].start_seconds == 12.5
    schema = RetrievalResult.model_json_schema()
    assert set(schema['properties']['items']['items']['discriminator']['mapping']) == {'document', 'video'}
    json.dumps(schema)


def test_mock_preserves_references_and_records_request(results):
    mock = MockRetriever([results])
    assert retrieve(mock) == results
    assert mock.calls[0].query == 'Bubble Sort'
    assert mock.calls[0].max_results == 5


def test_source_scope_and_limit(results):
    mock = MockRetriever([results, results, results])
    assert retrieve(mock, source_ids=['fixture-lecture']).items == [results.items[1]]
    assert retrieve(mock, max_results=1).items == [results.items[0]]
    assert retrieve(mock, source_ids=['missing']).items == []


def test_empty_results_are_successful_but_exhaustion_is_not():
    mock = MockRetriever([RetrievalResult()])
    assert retrieve(mock).items == []
    with pytest.raises(RetrievalError, match='No scripted') as failure:
        retrieve(mock)
    assert not failure.value.retryable


def test_scripted_failure_does_not_consume_next_result(results):
    mock = MockRetriever([RetrievalError(retryable=True), results.model_dump()])
    with pytest.raises(RetrievalError) as failure:
        retrieve(mock)
    assert failure.value.retryable
    assert retrieve(mock) == results


def test_mock_does_not_mutate_inputs_or_share_results(results):
    mock = MockRetriever([results, results])
    results.items[0].text = 'Changed'
    first = retrieve(mock)
    first.items[0].text = 'Changed again'
    second = retrieve(mock)
    assert second.items[0].text.startswith('Bubble Sort')
    request = RetrievalRequest(query='Original', source_ids=['fixture-notes'])
    recording = MockRetriever([{}])
    asyncio.run(recording.retrieve(request))
    request.source_ids.append('another')
    assert recording.calls[0].source_ids == ['fixture-notes']


@pytest.mark.parametrize('values', [
    {'query': ''}, {'query': ' \n'}, {'query': 'Sorting', 'source_ids': []},
    {'query': 'Sorting', 'source_ids': [' ']}, {'query': 'Sorting', 'max_results': 0},
    {'query': 'Sorting', 'max_results': '5'}, {'query': 'Sorting', 'extra': True},
])
def test_invalid_requests(values):
    with pytest.raises(ValidationError):
        RetrievalRequest(**values)


@pytest.mark.parametrize('start,end', [(-1.0, 1.0), (1.0, 1.0), (2.0, 1.0), (0.0, float('inf')), (float('nan'), 5.0)])
def test_invalid_timestamps(start, end):
    with pytest.raises(ValidationError):
        VideoSegment(
            source_id='v1', segment_id='s1', title='Lecture', transcript='Text',
            start_seconds=start, end_seconds=end,
        )


@pytest.mark.parametrize('overrides', [{'page': 0}, {'text': ' '}, {'source_id': ''}, {'page': '3'}])
def test_invalid_passages(overrides):
    with pytest.raises(ValidationError):
        DocumentPassage(**{
            'source_id': 'd1', 'passage_id': 'p1', 'title': 'Notes', 'text': 'Text',
            **overrides,
        })


def test_duplicate_references_are_rejected(results):
    with pytest.raises(ValidationError):
        RetrievalResult(items=[results.items[0], results.items[0]])


def test_multiple_passages_from_same_source_are_allowed(results):
    second = results.items[0].model_copy(update={'passage_id': 'another'})
    assert len(RetrievalResult(items=[results.items[0], second]).items) == 2


def test_invalid_mock_results_fail_safely():
    with pytest.raises(RetrievalError, match='invalid results'):
        retrieve(MockRetriever([{'items': [{'kind': 'invented', 'text': 'private text'}]}]))


def test_optional_locations_and_uris_are_preserved(results):
    data = results.model_dump()
    data['items'][0]['source_uri'] = 'library://notes'
    data['items'][1]['source_uri'] = 'media://lecture'
    mock = MockRetriever([data])
    retrieved = retrieve(mock)
    assert retrieved.items[0].source_uri == 'library://notes'
    assert retrieved.items[1].source_uri == 'media://lecture'
