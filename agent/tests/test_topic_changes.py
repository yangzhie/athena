import asyncio

import pytest

from athena_agent.conversation import ConversationTurn
from athena_agent.learning import ConceptMastery
from athena_agent.llm import DependencyError, LLMError

from .test_conversation_manager import setup


def test_explicit_change_archives_prior_topic_and_starts_fresh():
    context, store, mock, manager = setup([
        {'intent': 'topic_change', 'new_goal': 'Graph theory'},
        {'text': 'Let’s explore vertices.', 'discussion_focus': 'Vertices'},
    ])
    snapshot = store.read(context)
    snapshot.active_topic.learning_state.phase = 'reinforce'
    snapshot.active_topic.learning_state.current_concept_id = 'adjacency'
    snapshot.active_topic.learning_state.mastery = [
        ConceptMastery(concept_id='sorting', status='mastered', assessment_ids=['e1']),
    ]
    store._save(context, snapshot)
    store.update_focus(context, 'Old sorting focus')
    store.append_turn(context, ConversationTurn(user_text='Prior sorting question', assistant_text='Prior sorting explanation'))
    old = store.read(context).active_topic

    asyncio.run(manager.send(context, 'Switch to graph theory.'))
    session = store.read(context)
    assert session.archived_topics == [old]
    assert session.active_topic.topic_id != old.topic_id
    assert session.active_topic.learning_state.goal == 'Graph theory'
    assert session.active_topic.learning_state.phase == 'diagnose'
    assert session.active_topic.learning_state.mastery == []
    assert session.active_topic.learning_state.current_concept_id is None
    assert session.active_topic.discussion_focus == 'Vertices'
    assert len(session.active_topic.history) == 1
    assert len(session.history) == 2
    routing = '\n'.join(message.content for message in mock.calls[0].messages)
    reply_context = '\n'.join(message.content for message in mock.calls[1].messages)
    assert 'Prior sorting explanation' in routing
    for old_text in ['Prior sorting question', 'Prior sorting explanation', 'Old sorting focus', '"assessment_ids": ["e1"]']:
        assert old_text not in reply_context
    assert 'Graph theory' in reply_context
    session.archived_topics[0].learning_state.goal = 'Changed'
    assert store.read(context).archived_topics[0] == old


def test_failed_switch_does_not_archive_or_replace_topic():
    context, store, _, manager = setup([
        {'intent': 'topic_change', 'new_goal': 'Graphs'}, DependencyError('Unavailable'),
    ])
    before = store.read(context)
    with pytest.raises(LLMError):
        asyncio.run(manager.send(context, 'Switch to graphs.'))
    assert store.read(context) == before


def test_cancelled_switch_leaves_previous_topic_active():
    context, store, _, _ = setup([])
    before = store.read(context)

    class Provider:
        async def generate(self, messages, model):
            if model.__name__ == 'IntentDecision':
                return model(intent='topic_change', new_goal='Graphs')
            raise asyncio.CancelledError()

    from athena_agent.conversation_manager import ConversationManager
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(ConversationManager(store, Provider()).send(context, 'Switch to graphs.'))
    assert store.read(context) == before


def test_ambiguous_change_and_comparison_do_not_switch():
    context, store, _, manager = setup([
        {'intent': 'ambiguous', 'clarification_question': 'Do you want to switch topics?'},
        {'intent': 'continue'}, {'text': 'Graphs can illustrate sorting too.'},
    ])
    original_id = store.read(context).active_topic.topic_id
    asyncio.run(manager.send(context, 'What about graphs?'))
    asyncio.run(manager.send(context, 'I mean as an example.'))
    session = store.read(context)
    assert session.active_topic.topic_id == original_id
    assert session.archived_topics == []


def test_repeated_switches_keep_archives_in_order():
    context, store, _, manager = setup([
        {'intent': 'topic_change', 'new_goal': 'Graphs'}, {'text': 'Graph intro'},
        {'intent': 'topic_change', 'new_goal': 'Probability'}, {'text': 'Probability intro'},
    ])
    asyncio.run(manager.send(context, 'Switch to graphs.'))
    asyncio.run(manager.send(context, 'Switch to probability.'))
    session = store.read(context)
    assert [topic.learning_state.goal for topic in session.archived_topics] == ['Bubble Sort', 'Graphs']
    assert session.active_topic.learning_state.goal == 'Probability'
    assert len(session.history) == 2
    assert len(session.archived_topics[1].history) == 1
