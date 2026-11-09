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
