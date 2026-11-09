import asyncio
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from athena_agent.assessment import AssessmentService
from athena_agent.conversation import ConversationError
from athena_agent.conversation_manager import ConversationManager
from athena_agent.learning import MultipleChoiceAnswer, TextAnswer
from athena_agent.llm import DependencyError, InvalidOutputError, LLMError, MockLLM
from .test_assessment import OPEN, assessed_topic, service
from .test_evaluation import GRADE, TEXT, make_question
from .test_session_planning import planning_data


FOLLOWUP = {
    'prompt': 'Apply one Bubble Sort pass to [3, 1, 2] and explain each comparison.',
    'expected_reasoning': 'Swap 3 and 1, then 3 and 2, explaining why the largest value moves right.',
}


def assessed_selection(context, store):
    question = make_question(context, store, 'multiple_choice')
    assessor, _ = service(store, [])
    return asyncio.run(assessor.evaluate(context, MultipleChoiceAnswer(question_id=question.question_id, selected_choice_id='a')))


def test_successful_independent_followup_can_establish_mastery(assessed_topic):
    context, store = assessed_topic
    first = assessed_selection(context, store)
    assert store.read(context).active_topic.learning_state.mastery[0].status == 'developing'
    assessor, mock = service(store, [FOLLOWUP, GRADE])
    activity = asyncio.run(assessor.generate_followup(context, first.assessment_id))
    assert activity.question.kind == 'open_ended'
    assert activity.question.question_id != first.question_id
    assert activity.question.concept_id == first.concept_id
    assert activity.question.difficulty == 'intermediate'
    assert 'correct_choice_id' not in activity.model_dump_json()
    assert 'verification follow-up' in mock.calls[0].messages[0].content
    assert first.assessment_id in mock.calls[0].messages[1].content
    second = asyncio.run(assessor.evaluate(context, TextAnswer(question_id=activity.question.question_id, text=TEXT)))
    state = store.read(context).active_topic.learning_state
    assert state.mastery[0].status == 'mastered'
    assert state.mastery[0].assessment_ids == [first.assessment_id, second.assessment_id]
    assert state.phase == 'diagnose'


def test_contradictory_followup_does_not_label_the_previous_answer_a_guess(assessed_topic):
    context, store = assessed_topic
    first = assessed_selection(context, store)
    assessor, mock = service(store, [FOLLOWUP, {**GRADE, 'outcome': 'incorrect', 'feedback': 'The reasoning does not support the result.'}])
    activity = asyncio.run(assessor.generate_followup(context, first.assessment_id))
    result = asyncio.run(assessor.evaluate(context, TextAnswer(question_id=activity.question.question_id, text=TEXT)))
    assert result.outcome == 'incorrect'
    assert 'guess' not in result.feedback
    assert store.read(context).active_topic.learning_state.mastery[0].status == 'developing'
    assert 'Do not claim certainty' in mock.calls[1].messages[0].content


def test_followup_generation_is_idempotent(assessed_topic):
    context, store = assessed_topic
    parent = assessed_selection(context, store)
    assessor, mock = service(store, [FOLLOWUP])
    first = asyncio.run(assessor.generate_followup(context, parent.assessment_id))
    saved = store.read(context)
    second = asyncio.run(assessor.generate_followup(context, parent.assessment_id))
    assert first == second
    assert len(mock.calls) == 1
    assert store.read(context) == saved
    assert saved.active_topic.question_records[-1].parent_assessment_id == parent.assessment_id


@pytest.mark.parametrize('draft', [DependencyError('Unavailable'), {'prompt': 'Which pair should Bubble Sort swap?', 'expected_reasoning': 'Reason'}])
def test_failed_or_repeated_question_does_not_create_followup(assessed_topic, draft):
    context, store = assessed_topic
    parent = assessed_selection(context, store)
    assessor, _ = service(store, [draft])
    before = store.read(context)
    with pytest.raises(LLMError):
        asyncio.run(assessor.generate_followup(context, parent.assessment_id))
    assert store.read(context) == before


def test_followup_cancellation_is_atomic(assessed_topic):
    context, store = assessed_topic
    parent = assessed_selection(context, store)
    provider = AsyncMock()
    provider.generate.side_effect = asyncio.CancelledError()
    before = store.read(context)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(AssessmentService(store, provider).generate_followup(context, parent.assessment_id))
    assert store.read(context) == before


def test_topic_switch_keeps_old_evidence_private_and_new_topic_empty(assessed_topic):
    context, store = assessed_topic
    parent = assessed_selection(context, store)
    assessor, _ = service(store, [FOLLOWUP])
    followup = asyncio.run(assessor.generate_followup(context, parent.assessment_id))
    old = store.read(context).active_topic
    manager = ConversationManager(store, MockLLM([
        {'intent': 'topic_change', 'new_goal': 'Graph theory'}, {'text': 'Graph intro'},
    ]))
    asyncio.run(manager.send(context, 'Switch to graph theory.'))
    session = store.read(context)
    assert session.archived_topics[-1] == old
    assert session.active_topic.question_records == session.active_topic.assessment_records == []
    with pytest.raises(ConversationError, match='assessment'):
        asyncio.run(assessor.generate_followup(context, parent.assessment_id))
    with pytest.raises(ConversationError, match='question'):
        asyncio.run(assessor.evaluate(context, TextAnswer(question_id=followup.question.question_id, text=TEXT)))


def test_missing_assessment_and_removed_concept_do_not_call_model(assessed_topic):
    context, store = assessed_topic
    parent = assessed_selection(context, store)
    assessor, mock = service(store, [])
    with pytest.raises(ConversationError, match='assessment'):
        asyncio.run(assessor.generate_followup(context, 'missing'))
    draft = store.read(context)
    draft.active_topic.roadmap.graph.concepts.pop()
    store._save(context, draft)
    with pytest.raises(ConversationError, match='not in'):
        asyncio.run(assessor.generate_followup(context, parent.assessment_id))
    assert mock.calls == []


def test_invalid_parent_link_rejected_by_topic_validation(assessed_topic):
    context, store = assessed_topic
    parent = assessed_selection(context, store)
    assessor, _ = service(store, [FOLLOWUP])
    asyncio.run(assessor.generate_followup(context, parent.assessment_id))
    draft = store.read(context)
    draft.active_topic.question_records[-1].parent_assessment_id = 'missing'
    with pytest.raises(ValidationError):
        store._save(context, draft)


def test_concurrent_followup_generation_records_only_one_question(assessed_topic):
    context, store = assessed_topic
    parent = assessed_selection(context, store)

    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        calls = []

        class Provider:
            async def generate(self, messages, model):
                calls.append(model)
                entered.set()
                await release.wait()
                return model.model_validate(FOLLOWUP)

        first = asyncio.create_task(AssessmentService(store, Provider()).generate_followup(context, parent.assessment_id))
        await entered.wait()
        second = asyncio.create_task(AssessmentService(store, Provider()).generate_followup(context, parent.assessment_id))
        await asyncio.sleep(0)
        release.set()
        results = await asyncio.gather(first, second)
        assert results[0] == results[1]
        assert len(calls) == 1

    asyncio.run(run())
    assert len(store.read(context).active_topic.question_records) == 2
