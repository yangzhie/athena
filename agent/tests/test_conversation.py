import pytest
from pydantic import ValidationError

from athena_agent.contracts import RequestContext
from athena_agent.conversation import (
    ConversationError, ConversationTurn, InMemoryConversationStore, SessionNotFoundError,
)


def context(learner='learner', session='session'):
    return RequestContext(request_id='request', learner_id=learner, session_id=session)


def test_sessions_preserve_order_and_are_independent():
    store = InMemoryConversationStore()
    first = context()
    second = context(session='other')
    store.create(first)
    store.create(second)
    store.append_turn(first, ConversationTurn(user_text='First', assistant_text='One'))
    store.append_turn(first, ConversationTurn(user_text='Second', assistant_text='Two'))
    session = store.read(first)
    assert [turn.user_text for turn in session.history] == ['First', 'Second']
    assert [message.role for message in session.history[0].messages()] == ['user', 'assistant']
    assert store.read(second).history == []


def test_sessions_return_deep_snapshots():
    store = InMemoryConversationStore()
    created = store.create(context())
    created.history.append(ConversationTurn(user_text='Fake', assistant_text='Fake'))
    turn = ConversationTurn(user_text='Original', assistant_text='Reply')
    result = store.append_turn(context(), turn)
    turn.user_text = result.history[0].assistant_text = 'Changed'
    read = store.read(context())
    read.history.clear()
    assert store.read(context()).history[0].model_dump() == {'user_text': 'Original', 'assistant_text': 'Reply'}


def test_missing_and_cross_learner_sessions_are_indistinguishable():
    store = InMemoryConversationStore()
    store.create(context())
    for request in [context(learner='other'), context(session='missing')]:
        with pytest.raises(SessionNotFoundError, match='unavailable') as failure:
            store.read(request)
        assert failure.value.code == 'session_not_found'


def test_duplicate_session_rejected_without_resetting_history():
    store = InMemoryConversationStore()
    store.create(context())
    store.append_turn(context(), ConversationTurn(user_text='Keep', assistant_text='Reply'))
    with pytest.raises(ConversationError, match='already exists'):
        store.create(context())
    assert len(store.read(context()).history) == 1


def test_session_id_required():
    with pytest.raises(ConversationError, match='session ID'):
        InMemoryConversationStore().create(context(session=None))


@pytest.mark.parametrize('data', [{'user_text': ' ', 'assistant_text': 'Hi'}, {'user_text': 'Hi', 'assistant_text': ''}, {'user_text': 'Hi', 'assistant_text': 'Hi', 'role': 'system'}])
def test_turns_are_complete_and_user_assistant_only(data):
    with pytest.raises(ValidationError):
        ConversationTurn(**data)


def test_initial_goal_uses_learning_state_and_unique_topic_id():
    store = InMemoryConversationStore()
    store.create(context())
    first = store.initialize_goal(context(), 'Sorting')
    assert first.active_topic.learning_state.goal == 'Sorting'
    assert first.active_topic.learning_state.phase == 'diagnose'
    assert first.active_topic.learning_state.mastery == []
    assert first.active_topic.discussion_focus is None
    store.create(context(session='other'))
    second = store.initialize_goal(context(session='other'), 'Graphs')
    assert first.active_topic.topic_id != second.active_topic.topic_id


def test_focus_and_history_do_not_change_learning_evidence():
    store = InMemoryConversationStore()
    store.create(context())
    initial = store.initialize_goal(context(), 'Sorting')
    store.update_focus(context(), 'Adjacent comparisons')
    store.append_turn(context(), ConversationTurn(user_text='Why?', assistant_text='To compare.'))
    updated = store.read(context())
    assert updated.active_topic.learning_state == initial.active_topic.learning_state
    assert updated.active_topic.discussion_focus == 'Adjacent comparisons'
    assert updated.active_topic.history == updated.history
    assert store.update_focus(context(), None).active_topic.discussion_focus is None


def test_invalid_goal_and_focus_leave_session_unchanged():
    store = InMemoryConversationStore()
    store.create(context())
    with pytest.raises(ConversationError, match='Initialize'):
        store.update_focus(context(), 'Focus')
    with pytest.raises(ValidationError):
        store.initialize_goal(context(), ' ')
    assert store.read(context()).active_topic is None
    initial = store.initialize_goal(context(), 'Sorting')
    with pytest.raises(ConversationError, match='already has'):
        store.initialize_goal(context(), 'Graphs')
    with pytest.raises(ValidationError):
        store.update_focus(context(), ' ')
    assert store.read(context()) == initial


def test_topic_snapshot_does_not_share_state_or_history():
    store = InMemoryConversationStore()
    store.create(context())
    store.append_turn(context(), ConversationTurn(user_text='Before goal', assistant_text='Reply'))
    snapshot = store.initialize_goal(context(), 'Sorting')
    snapshot.active_topic.learning_state.goal = 'Changed'
    snapshot.active_topic.history.append(ConversationTurn(user_text='Fake', assistant_text='Fake'))
    stored = store.read(context())
    assert stored.active_topic.learning_state.goal == 'Sorting'
    assert stored.active_topic.history == []
    assert len(stored.history) == 1
