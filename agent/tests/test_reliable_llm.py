import asyncio
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from athena_agent.learning import CompletionActivity, QuestionWithCriteria
from athena_agent.llm import DependencyError, InvalidOutputError, LLMError, Message, MockLLM, ModelRefusalError
from athena_agent.reliable_llm import ReliableLLM, RetryPolicy


MESSAGES = [Message(role='user', content='Teach sorting')]
VALID = {'activity_id': 'a1', 'text': 'Ready'}


def generate(llm):
    return asyncio.run(llm.generate(MESSAGES, CompletionActivity))


def test_transient_failure_then_success():
    provider = MockLLM([DependencyError('private detail', retryable=True), VALID])
    sleep = AsyncMock()
    assert generate(ReliableLLM(provider, sleeper=sleep)).text == 'Ready'
    assert len(provider.calls) == 2
    sleep.assert_awaited_once_with(0.5)


def test_exact_attempt_limit_and_backoff():
    provider = MockLLM([DependencyError('private', retryable=True) for _ in range(4)])
    sleep = AsyncMock()
    with pytest.raises(DependencyError) as failure:
        generate(ReliableLLM(provider, sleeper=sleep))
    assert len(provider.calls) == 3
    assert [call.args[0] for call in sleep.await_args_list] == [0.5, 1.0]
    assert 'private' not in str(failure.value)
    assert failure.value.retryable
    assert failure.value.__suppress_context__


@pytest.mark.parametrize('failure', [DependencyError('private'), ModelRefusalError(), LLMError('private'), RuntimeError('private')])
def test_terminal_failures_do_not_retry(failure):
    provider = AsyncMock()
    provider.generate.side_effect = failure
    sleep = AsyncMock()
    with pytest.raises(LLMError) as caught:
        generate(ReliableLLM(provider, sleeper=sleep))
    assert provider.generate.await_count == 1
    sleep.assert_not_awaited()
    assert 'private' not in str(caught.value)
    assert not caught.value.retryable


def test_invalid_output_is_retried():
    provider = MockLLM(['not json', VALID])
    sleep = AsyncMock()
    assert generate(ReliableLLM(provider, sleeper=sleep)).text == 'Ready'
    sleep.assert_awaited_once_with(0.5)


@pytest.mark.parametrize('result', [
    None, VALID, 'raw text',
    CompletionActivity.model_construct(activity_id='a1', text=' '),
])
def test_invalid_return_values_are_revalidated(result):
    provider = AsyncMock()
    provider.generate.return_value = result
    sleep = AsyncMock()
    with pytest.raises(InvalidOutputError):
        generate(ReliableLLM(provider, sleeper=sleep))
    assert provider.generate.await_count == 3


def test_cross_field_invariants_are_rechecked():
    bundle = QuestionWithCriteria.model_validate({
        'question': {
            'kind': 'multiple_choice', 'question_id': 'q1', 'concept_id': 'sorting',
            'prompt': 'Which?', 'difficulty': 'beginner',
            'choices': [{'choice_id': 'a', 'text': 'A'}, {'choice_id': 'b', 'text': 'B'}],
        },
        'criteria': {'kind': 'multiple_choice', 'correct_choice_id': 'a', 'rationale': 'Reason'},
    })
    bundle.criteria.correct_choice_id = 'missing'
    provider = AsyncMock()
    provider.generate.return_value = bundle
    with pytest.raises(InvalidOutputError):
        asyncio.run(ReliableLLM(provider, sleeper=AsyncMock()).generate(MESSAGES, QuestionWithCriteria))
    assert provider.generate.await_count == 3


def test_custom_policy_caps_delays():
    provider = MockLLM([DependencyError('Busy', retryable=True) for _ in range(4)] + [VALID])
    sleep = AsyncMock()
    policy = RetryPolicy(max_attempts=5, initial_delay=1.0, max_delay=2.0)
    assert generate(ReliableLLM(provider, policy=policy, sleeper=sleep)).text == 'Ready'
    assert [call.args[0] for call in sleep.await_args_list] == [1.0, 2.0, 2.0, 2.0]


def test_one_attempt_has_no_delay():
    sleep = AsyncMock()
    with pytest.raises(InvalidOutputError):
        generate(ReliableLLM(MockLLM(['bad']), policy=RetryPolicy(max_attempts=1), sleeper=sleep))
    sleep.assert_not_awaited()


def test_success_has_no_delay():
    sleep = AsyncMock()
    assert generate(ReliableLLM(MockLLM([VALID]), sleeper=sleep)).text == 'Ready'
    sleep.assert_not_awaited()


@pytest.mark.parametrize('policy', [
    {'max_attempts': 0}, {'max_attempts': True}, {'initial_delay': -1.0},
    {'max_delay': float('inf')}, {'max_attempts': '3'},
])
def test_invalid_policy(policy):
    with pytest.raises(ValidationError):
        RetryPolicy(**policy)


def test_cancellation_propagates_without_retry():
    provider = AsyncMock()
    provider.generate.side_effect = asyncio.CancelledError()
    sleep = AsyncMock()
    with pytest.raises(asyncio.CancelledError):
        generate(ReliableLLM(provider, sleeper=sleep))
    assert provider.generate.await_count == 1
    sleep.assert_not_awaited()


def test_cancellation_during_backoff_propagates():
    provider = MockLLM([DependencyError('Busy', retryable=True), VALID])
    sleep = AsyncMock(side_effect=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        generate(ReliableLLM(provider, sleeper=sleep))
    assert len(provider.calls) == 1


def test_messages_unchanged_between_attempts():
    seen = []

    class MutatingProvider:
        async def generate(self, messages, response_model):
            seen.append(messages[0].content)
            messages[0].content = 'Changed'
            if len(seen) == 1:
                raise DependencyError('Busy', retryable=True)
            return response_model(**VALID)

    assert generate(ReliableLLM(MutatingProvider(), sleeper=AsyncMock())).text == 'Ready'
    assert seen == ['Teach sorting', 'Teach sorting']
    assert MESSAGES[0].content == 'Teach sorting'
