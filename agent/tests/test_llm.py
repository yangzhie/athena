import asyncio

import pytest

from athena_agent.learning import CompletionActivity
from athena_agent.llm import DependencyError, InvalidOutputError, Message, MockLLM, ModelRefusalError


def generate(mock):
    return asyncio.run(mock.generate([Message(role='user', content='Teach sorting')], CompletionActivity))


def test_scripted_outputs_are_consumed_in_order():
    mock = MockLLM([
        {'activity_id': 'a1', 'text': 'First'},
        '{"activity_id":"a2","text":"Second"}',
        CompletionActivity(activity_id='a3', text='Third'),
    ])
    assert [generate(mock).text for _ in range(3)] == ['First', 'Second', 'Third']
    assert len(mock.calls) == 3
    assert mock.calls[0].response_model is CompletionActivity
    assert mock.calls[0].messages[0].content == 'Teach sorting'
    with pytest.raises(DependencyError, match='No scripted') as failure:
        generate(mock)
    assert failure.value.retryable is False


@pytest.mark.parametrize('output', ['broken json', {'activity_id': 'a1', 'text': 12}])
def test_invalid_scripted_output_is_safe(output):
    with pytest.raises(InvalidOutputError) as failure:
        generate(MockLLM([output]))
    assert failure.value.retryable is True
    assert failure.value.code == 'invalid_model_output'


def test_scripted_failure_does_not_consume_next_result():
    mock = MockLLM([DependencyError('Unavailable', retryable=True), {'activity_id': 'a1', 'text': 'Ready'}])
    with pytest.raises(DependencyError) as failure:
        generate(mock)
    assert failure.value.retryable
    assert generate(mock).text == 'Ready'


def test_mock_snapshots_inputs_and_records_calls():
    data = {'activity_id': 'a1', 'text': 'Original'}
    mock = MockLLM([data])
    data['text'] = 'Changed'
    message = Message(role='user', content='Original')
    result = asyncio.run(mock.generate([message], CompletionActivity))
    message.content = 'Changed'
    assert result.text == mock.calls[0].messages[0].content == 'Original'


def test_refusal_is_terminal():
    with pytest.raises(ModelRefusalError) as failure:
        generate(MockLLM([ModelRefusalError()]))
    assert not failure.value.retryable
