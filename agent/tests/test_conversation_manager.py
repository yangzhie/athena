import asyncio
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from athena_agent.contracts import RequestContext
from athena_agent.conversation import ConversationError, ConversationTurn, InMemoryConversationStore
from athena_agent.conversation_manager import ConversationManager, IntentDecision
from athena_agent.llm import DependencyError, LLMError, MockLLM


def setup(responses):
    context = RequestContext(request_id='r1', learner_id='l1', session_id='s1')
    store = InMemoryConversationStore()
    store.create(context)
    store.initialize_goal(context, 'Bubble Sort')
    mock = MockLLM(responses)
    return context, store, mock, ConversationManager(store, mock)


def test_followup_has_context_and_commits_one_turn():
    context, store, mock, manager = setup([
        {'intent': 'continue'}, {'text': 'Compare neighbours.', 'discussion_focus': 'Comparisons'},
    ])
    store.append_turn(context, ConversationTurn(user_text='What is a pass?', assistant_text='A traversal.'))
    initial = store.read(context)
    reply = asyncio.run(manager.send(context, 'Why?'))
    assert reply.text == 'Compare neighbours.'
    for call in mock.calls:
        contents = [message.content for message in call.messages]
        assert 'What is a pass?' in contents
        assert 'A traversal.' in contents
        assert contents[-1] == 'Why?'
        assert 'Bubble Sort' in contents[1]
    updated = store.read(context)
    assert len(updated.history) == 2
    assert updated.active_topic.discussion_focus == 'Comparisons'
    assert updated.active_topic.learning_state == initial.active_topic.learning_state


def test_request_for_explanation_keeps_goal():
    context, store, _, manager = setup([
        {'intent': 'clarification'}, {'text': 'A pass visits each pair.'},
    ])
    asyncio.run(manager.send(context, 'Explain that more simply.'))
    assert store.read(context).active_topic.learning_state.goal == 'Bubble Sort'


def test_ambiguous_intent_asks_without_changing_focus():
    context, store, mock, manager = setup([
        {'intent': 'ambiguous', 'clarification_question': 'Do you mean graphs or sorting?'},
    ])
    store.update_focus(context, 'Sorting passes')
    before = store.read(context)
    reply = asyncio.run(manager.send(context, 'What about that other thing?'))
    assert reply.text == 'Do you mean graphs or sorting?'
    after = store.read(context)
    assert after.active_topic.learning_state == before.active_topic.learning_state
    assert after.active_topic.discussion_focus == 'Sorting passes'
    assert len(mock.calls) == 1


@pytest.mark.parametrize('responses', [
    [DependencyError('Unavailable')],
    [{'intent': 'continue'}, DependencyError('Unavailable')],
])
def test_failures_do_not_record_partial_turns(responses):
    context, store, _, manager = setup(responses)
    before = store.read(context)
    with pytest.raises(LLMError):
        asyncio.run(manager.send(context, 'Why?'))
    assert store.read(context) == before


def test_cancellation_rolls_back():
    context, store, _, _ = setup([])
    before = store.read(context)
    provider = AsyncMock()
    provider.generate.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(ConversationManager(store, provider).send(context, 'Why?'))
    assert store.read(context) == before


def test_blank_message_and_missing_goal_do_not_call_model():
    context, store, mock, manager = setup([])
    with pytest.raises(ValidationError):
        asyncio.run(manager.send(context, ' '))
    other = context.model_copy(update={'session_id': 'other'})
    store.create(other)
    with pytest.raises(ConversationError, match='Initialize'):
        asyncio.run(manager.send(other, 'Hi'))
    assert mock.calls == []


def test_concurrent_managers_share_session_lock():
    async def run():
        context, store, _, _ = setup([])
        started = asyncio.Event()
        release = asyncio.Event()
        order = []

        class Provider:
            async def generate(self, messages, model):
                text = messages[-1].content
                order.append(text)
                if model is IntentDecision:
                    if text == 'First':
                        started.set()
                        await release.wait()
                    return model(intent='continue')
                if text == 'Second':
                    assert any(message.content == 'Reply to First' for message in messages)
                return model(text='Reply to ' + text)

        provider = Provider()
        first = asyncio.create_task(ConversationManager(store, provider).send(context, 'First'))
        await started.wait()
        second = asyncio.create_task(ConversationManager(store, provider).send(context, 'Second'))
        await asyncio.sleep(0)
        assert order == ['First']
        release.set()
        await asyncio.gather(first, second)
        assert [turn.user_text for turn in store.read(context).history] == ['First', 'Second']

    asyncio.run(run())


def test_out_of_band_change_is_not_overwritten():
    context, store, _, _ = setup([])

    class Provider:
        async def generate(self, messages, model):
            if model is IntentDecision:
                return model(intent='continue')
            store.update_focus(context, 'External change')
            return model(text='Reply')

    with pytest.raises(ConversationError, match='session changed'):
        asyncio.run(ConversationManager(store, Provider()).send(context, 'Hi'))
    result = store.read(context)
    assert result.history == []
    assert result.active_topic.discussion_focus == 'External change'


@pytest.mark.parametrize('values', [
    {'intent': 'topic_change'}, {'intent': 'continue', 'new_goal': 'Graphs'},
    {'intent': 'ambiguous'}, {'intent': 'clarification', 'clarification_question': 'What?'},
])
def test_intent_output_constraints(values):
    with pytest.raises(ValidationError):
        IntentDecision(**values)
