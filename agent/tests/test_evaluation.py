import asyncio
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from athena_agent.assessment import AssessmentService
from athena_agent.assessment_models import AssessmentPolicy
from athena_agent.conversation import ConversationError
from athena_agent.learning import MultipleChoiceAnswer, TextAnswer
from athena_agent.llm import DependencyError, InvalidOutputError, LLMError
from .test_assessment import MC, OPEN, assessed_topic, service
from .test_session_planning import planning_data


TEXT = 'Adjacent comparisons move the larger value right.'
GRADE = {'outcome': 'correct', 'feedback': 'You explain the movement of the larger value.', 'confidence': 0.9, 'evidence_quotes': ['larger value right']}


def make_question(context, store, kind='open_ended'):
    assessor, _ = service(store, [OPEN if kind == 'open_ended' else MC])
    return asyncio.run(getattr(assessor, 'generate_' + kind)(context, 'bubble-sort')).question


@pytest.mark.parametrize('choice,outcome', [('a', 'correct'), ('b', 'incorrect')])
def test_multiple_choice_grading_is_deterministic(assessed_topic, choice, outcome):
    context, store = assessed_topic
    question = make_question(context, store, 'multiple_choice')
    assessor, mock = service(store, [])
    answer = MultipleChoiceAnswer(question_id=question.question_id, selected_choice_id=choice)
    assessment = asyncio.run(assessor.evaluate(context, answer))
    assert assessment.outcome == outcome
    assert assessment.confidence == 1.0
    assert mock.calls == []
    assert len(store.read(context).active_topic.assessment_records) == 1


@pytest.mark.parametrize('outcome', ['correct', 'partial', 'incorrect', 'uncertain'])
def test_open_answer_outcomes_are_recorded(assessed_topic, outcome):
    context, store = assessed_topic
    question = make_question(context, store)
    assessor, mock = service(store, [{**GRADE, 'outcome': outcome}])
    before = store.read(context)
    assessment = asyncio.run(assessor.evaluate(context, TextAnswer(question_id=question.question_id, text=TEXT)))
    assert assessment.outcome == outcome
    assert assessment.question_id == question.question_id
    assert assessment.concept_id == 'bubble-sort'
    assert 'expected_reasoning' in mock.calls[0].messages[1].content
    after = store.read(context)
    assert after.history == before.history
    assert after.active_topic.learning_state == before.active_topic.learning_state
    assert after.active_topic.assessment_records[0].evidence_quotes == GRADE['evidence_quotes']


def test_low_confidence_is_uncertain_and_threshold_configurable(assessed_topic):
    context, store = assessed_topic
    question = make_question(context, store)
    assessor, _ = service(store, [{**GRADE, 'confidence': 0.79}])
    assert asyncio.run(assessor.evaluate(context, TextAnswer(question_id=question.question_id, text=TEXT))).outcome == 'uncertain'
    question = make_question(context, store)
    assessor, _ = service(store, [{**GRADE, 'confidence': 0.79}], policy=AssessmentPolicy(evaluation_confidence_threshold=0.7))
    assert asyncio.run(assessor.evaluate(context, TextAnswer(question_id=question.question_id, text=TEXT))).outcome == 'correct'


def test_identical_retry_returns_saved_result_and_changed_submission_rejected(assessed_topic):
    context, store = assessed_topic
    question = make_question(context, store)
    assessor, mock = service(store, [GRADE])
    answer = TextAnswer(question_id=question.question_id, text=TEXT)
    first = asyncio.run(assessor.evaluate(context, answer))
    snapshot = store.read(context)
    assert asyncio.run(assessor.evaluate(context, answer)) == first
    assert len(mock.calls) == 1
    assert store.read(context) == snapshot
    for changed, hints in [(answer.model_copy(update={'text': 'Different'}), False), (answer, True)]:
        with pytest.raises(ConversationError, match='fresh question'):
            asyncio.run(assessor.evaluate(context, changed, hint_used=hints))
    first.feedback = 'Mutated'
    assert store.read(context).active_topic.assessment_records[0].assessment.feedback != 'Mutated'


def test_invalid_answer_formats_and_choices_never_call_model(assessed_topic):
    context, store = assessed_topic
    mc = make_question(context, store, 'multiple_choice')
    opened = make_question(context, store)
    assessor, mock = service(store, [])
    for answer in [
        TextAnswer(question_id=mc.question_id, text='a'),
        MultipleChoiceAnswer(question_id=mc.question_id, selected_choice_id='missing'),
        MultipleChoiceAnswer(question_id=opened.question_id, selected_choice_id='a'),
        TextAnswer(question_id='missing', text='Hi'),
    ]:
        with pytest.raises(ConversationError):
            asyncio.run(assessor.evaluate(context, answer))
    with pytest.raises(ValidationError):
        asyncio.run(assessor.evaluate(context, TextAnswer(question_id=opened.question_id, text=TEXT), hint_used='false'))
    assert mock.calls == []
    assert store.read(context).active_topic.assessment_records == []


@pytest.mark.parametrize('result', [DependencyError('Unavailable'), {**GRADE, 'evidence_quotes': ['invented quote']}, {**GRADE, 'evidence_quotes': []}])
def test_failed_evaluation_records_nothing(assessed_topic, result):
    context, store = assessed_topic
    question = make_question(context, store)
    assessor, _ = service(store, [result])
    before = store.read(context)
    with pytest.raises(LLMError):
        asyncio.run(assessor.evaluate(context, TextAnswer(question_id=question.question_id, text=TEXT)))
    assert store.read(context) == before


def test_cancelled_evaluation_records_nothing(assessed_topic):
    context, store = assessed_topic
    question = make_question(context, store)
    provider = AsyncMock()
    provider.generate.side_effect = asyncio.CancelledError()
    before = store.read(context)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(AssessmentService(store, provider).evaluate(context, TextAnswer(question_id=question.question_id, text=TEXT)))
    assert store.read(context) == before


def test_question_for_removed_concept_cannot_receive_new_assessment(assessed_topic):
    context, store = assessed_topic
    question = make_question(context, store)
    snapshot = store.read(context)
    snapshot.active_topic.roadmap.graph.concepts.pop()
    store._save(context, snapshot)
    assessor, mock = service(store, [])
    with pytest.raises(ConversationError, match='not in'):
        asyncio.run(assessor.evaluate(context, TextAnswer(question_id=question.question_id, text=TEXT)))
    assert mock.calls == []


def test_low_confidence_without_quotes_is_still_uncertain(assessed_topic):
    context, store = assessed_topic
    question = make_question(context, store)
    assessor, _ = service(store, [{**GRADE, 'confidence': 0.4, 'evidence_quotes': []}])
    result = asyncio.run(assessor.evaluate(context, TextAnswer(question_id=question.question_id, text=TEXT)))
    assert result.outcome == 'uncertain'


def test_stale_evaluation_does_not_overwrite_newer_context(assessed_topic):
    context, store = assessed_topic
    question = make_question(context, store)

    class Provider:
        async def generate(self, messages, model):
            store.update_focus(context, 'Newer focus')
            return model.model_validate(GRADE)

    with pytest.raises(ConversationError, match='session changed'):
        asyncio.run(AssessmentService(store, Provider()).evaluate(context, TextAnswer(question_id=question.question_id, text=TEXT)))
    assert store.read(context).active_topic.assessment_records == []
    assert store.read(context).active_topic.discussion_focus == 'Newer focus'


def test_concurrent_identical_submissions_produce_one_assessment(assessed_topic):
    context, store = assessed_topic
    question = make_question(context, store)
    answer = TextAnswer(question_id=question.question_id, text=TEXT)

    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        calls = []

        class Provider:
            async def generate(self, messages, model):
                calls.append(model)
                entered.set()
                await release.wait()
                return model.model_validate(GRADE)

        first = asyncio.create_task(AssessmentService(store, Provider()).evaluate(context, answer))
        await entered.wait()
        second = asyncio.create_task(AssessmentService(store, Provider()).evaluate(context, answer))
        await asyncio.sleep(0)
        release.set()
        results = await asyncio.gather(first, second)
        assert results[0] == results[1]
        assert len(calls) == 1

    asyncio.run(run())
    assert len(store.read(context).active_topic.assessment_records) == 1
