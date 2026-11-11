import asyncio

import pytest
from pydantic import ValidationError

from athena_agent.context import ContextBudget, ContextBudgetError, ContextBuilder, UTF8ByteCounter
from athena_agent.conversation import ConversationTurn, TopicContext
from athena_agent.conversation_manager import ConversationManager, ConversationReply, IntentDecision
from athena_agent.learning import ConceptMastery, LearningState
from .test_conversation_manager import setup


def topic_with_turns():
    return TopicContext(
        learning_state=LearningState(goal='Sorting', current_concept_id='comparison', mastery=[
            ConceptMastery(concept_id='comparison', status='developing', assessment_ids=['e1']),
        ]),
        discussion_focus='Comparisons',
        history=[
            ConversationTurn(user_text='First question ' * 20, assistant_text='First reply ' * 20),
            ConversationTurn(user_text='Latest question', assistant_text='Latest reply'),
        ],
    )


def builder_for(window):
    return ContextBuilder(ContextBudget(
        context_window=window, output_reserve=100, framing_allowance=50, per_message_allowance=10,
    ))


def test_default_counter_counts_utf8_bytes():
    assert UTF8ByteCounter().count('hello') == 5
    assert UTF8ByteCounter().count('你好') == 6


def test_recent_complete_turns_fit_at_exact_boundary():
    topic = topic_with_turns()
    recent_only = topic.model_copy(deep=True)
    recent_only.history = recent_only.history[-1:]
    generous = builder_for(100000)
    expected = generous.build(recent_only, 'Why?', 'Instructions', ConversationReply)
    exact = generous.estimated_tokens(expected, ConversationReply)
    builder = builder_for(exact)
    before = topic.model_dump()
    actual = builder.build(topic, 'Why?', 'Instructions', ConversationReply)
    assert actual == expected
    assert builder.estimated_tokens(actual, ConversationReply) == exact
    assert topic.model_dump() == before
    contents = '\n'.join(message.content for message in actual)
    for required in ['Sorting', 'Comparisons', 'comparison', 'e1', 'Instructions', 'Why?', 'Latest reply']:
        assert required in contents
    assert 'First question' not in contents
    assert actual[-1].content == 'Why?'
    assert [message.role for message in actual[2:-1]] == ['user', 'assistant']


def test_does_not_skip_newest_oversized_turn_to_include_older_history():
    topic = topic_with_turns()
    topic.history.reverse()  # Newest turn is deliberately much larger.
    no_history = topic.model_copy(deep=True)
    no_history.history = []
    generous = builder_for(100000)
    mandatory = generous.build(no_history, 'Why?', 'Instructions', ConversationReply)
    builder = builder_for(generous.estimated_tokens(mandatory, ConversationReply) + 100)
    actual = builder.build(topic, 'Why?', 'Instructions', ConversationReply)
    assert actual == mandatory


def test_mandatory_context_exact_boundary_and_one_less():
    topic = topic_with_turns()
    topic.history = []
    generous = builder_for(100000)
    mandatory = generous.build(topic, 'Why?', 'Instructions', ConversationReply)
    exact = generous.estimated_tokens(mandatory, ConversationReply)
    assert builder_for(exact).build(topic, 'Why?', 'Instructions', ConversationReply) == mandatory
    with pytest.raises(ContextBudgetError) as failure:
        builder_for(exact - 1).build(topic, 'Why?', 'Instructions', ConversationReply)
    assert failure.value.code == 'invalid_request'


def test_schema_and_output_allowance_are_counted():
    class Counter:
        def __init__(self):
            self.inputs = []
        def count(self, text):
            self.inputs.append(text)
            return 10

    counter = Counter()
    builder = ContextBuilder(ContextBudget(context_window=10000, output_reserve=100, framing_allowance=50, per_message_allowance=10), counter=counter)
    messages = builder.build(topic_with_turns(), 'Why?', 'Instructions', ConversationReply)
    counter.inputs.clear()
    assert builder.estimated_tokens(messages, ConversationReply) == 20 + 100 + 50 + len(messages) * 10
    assert 'discussion_focus' in counter.inputs[1]  # Response schema is measured separately.


@pytest.mark.parametrize('values', [
    {'context_window': 0}, {'context_window': 100, 'output_reserve': 100},
    {'output_reserve': -1}, {'per_message_allowance': -1}, {'context_window': True},
])
def test_invalid_budget(values):
    with pytest.raises(ValidationError):
        ContextBudget(**values)


@pytest.mark.parametrize('count', [-1, 1.5, True])
def test_invalid_counter_result(count):
    class Counter:
        def count(self, text):
            return count
    with pytest.raises(ValueError, match='nonnegative integer'):
        ContextBuilder(counter=Counter()).build(topic_with_turns(), 'Why?', 'Instructions', ConversationReply)


def test_oversized_message_fails_before_model_call_and_keeps_session():
    context, store, mock, _ = setup([])
    manager = ConversationManager(store, mock, context_builder=builder_for(5000))
    before = store.read(context)
    with pytest.raises(ContextBudgetError):
        asyncio.run(manager.send(context, 'x' * 10000))
    assert mock.calls == []
    assert store.read(context) == before


def test_oversized_learning_state_is_not_silently_removed():
    topic = topic_with_turns()
    topic.learning_state.goal = 'x' * 10000
    with pytest.raises(ContextBudgetError):
        builder_for(5000).build(topic, 'Hi', 'Instructions', ConversationReply)


def test_history_selection_does_not_delete_stored_turns():
    context, store, mock, _ = setup([
        {'intent': 'continue'}, {'text': 'Concise reply', 'discussion_focus': 'Focus'},
    ])
    for index in range(10):
        store.append_turn(context, ConversationTurn(user_text=f'Old {index} ' + 'x' * 2000, assistant_text='y' * 2000))
    manager = ConversationManager(store, mock, context_builder=builder_for(6000))
    asyncio.run(manager.send(context, 'Why?'))
    assert len(store.read(context).history) == 11
    assert len(store.read(context).active_topic.history) == 11
    for call in mock.calls:
        assert manager.context_builder.estimated_tokens(list(call.messages), call.response_model) <= 6000
        assert 'Old 0 ' not in '\n'.join(message.content for message in call.messages)


def test_reply_budget_failure_after_routing_rolls_back():
    from athena_agent.answers import ReplyDraft
    context, store, _, _ = setup([])

    class Builder(ContextBuilder):
        def build(self, topic, text, instructions, model):
            if model is ReplyDraft:
                raise ContextBudgetError()
            return super().build(topic, text, instructions, model)

    from athena_agent.llm import MockLLM
    mock = MockLLM([{'intent': 'topic_change', 'new_goal': 'Graphs'}])
    manager = ConversationManager(store, mock, context_builder=Builder())
    before = store.read(context)
    with pytest.raises(ContextBudgetError):
        asyncio.run(manager.send(context, 'Switch to graphs.'))
    assert len(mock.calls) == 1
    assert store.read(context) == before
