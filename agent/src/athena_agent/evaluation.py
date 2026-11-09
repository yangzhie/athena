"""Repeatable offline behavioral evaluations, with no model credentials or network."""

import asyncio
import json
from pathlib import Path

from .assessment import AssessmentService
from .contracts import RequestContext
from .conversation import InMemoryConversationStore
from .learning import MultipleChoiceAnswer
from .llm import MockLLM
from .roadmap import Roadmap
from .teaching import TeachingService


async def evaluate_teaching(fixture: dict) -> dict:
    context = RequestContext(request_id='evaluation', learner_id='fixture', session_id='fixture')
    store = InMemoryConversationStore()
    store.create(context)
    store.initialize_goal(context, 'Bubble Sort')
    session = store.read(context)
    session.active_topic.roadmap = Roadmap.model_validate({
        'goal': 'Bubble Sort', 'scope': {'scope': 'narrow', 'rationale': 'One algorithm'},
        'graph': {'partial_coverage': False, 'concepts': [{
            'concept_id': 'bubble-sort', 'title': 'Bubble Sort', 'description': 'Adjacent comparisons',
            'objectives': ['Apply adjacent swaps'], 'difficulty': 'beginner',
        }]},
    })
    store._save(context, session)
    assessor = AssessmentService(store, MockLLM([fixture['question']]))
    question = await assessor.generate_multiple_choice(context, 'bubble-sort')
    assessment = await assessor.evaluate(context, MultipleChoiceAnswer(question_id=question.question.question_id, selected_choice_id='b'))
    before = store.read(context)
    activity = await TeachingService(store, MockLLM([fixture['explanation']])).explain(context, assessment.assessment_id)
    checks = {
        'targeted_concept': activity.concept_id == assessment.concept_id,
        'concise': len(activity.text.split()) <= 120 and len(activity.text) <= 1000,
        'no_mastery_side_effects': store.read(context) == before,
        'private_criteria_excluded': 'correct_choice_id' not in activity.model_dump_json(),
    }
    return {'scenario': 'targeted_teaching', 'passed': all(checks.values()), 'checks': checks}


async def evaluate_start(fixture: dict) -> dict:
    from .orchestrator import LearningOrchestrator
    context = RequestContext(request_id='evaluation', learner_id='fixture', session_id='fixture')
    store = InMemoryConversationStore()
    activity = await LearningOrchestrator(store, MockLLM(fixture['responses'])).start(
        context, fixture['goal'], difficulty=fixture['difficulty'],
    )
    topic = store.read(context).active_topic
    checks = {
        'proactive_diagnostic': activity.kind == 'question' and topic.current_activity == activity,
        'scope': topic.roadmap.scope.scope == fixture['scope'],
        'difficulty': activity.question.difficulty == fixture['difficulty'],
        'concept': activity.question.concept_id == fixture['concept_id'],
        'no_invented_mastery': topic.learning_state.mastery == [],
        'broad_partial': fixture['scope'] != 'broad' or topic.roadmap.graph.partial_coverage,
    }
    return {'scenario': fixture['name'], 'passed': all(checks.values()), 'checks': checks}


async def evaluate_assessment_loop(fixture: dict) -> dict:
    from .learning import TextAnswer
    from .orchestrator import LearningOrchestrator
    context = RequestContext(request_id='evaluation', learner_id='fixture', session_id='fixture')
    store = InMemoryConversationStore()
    llm = MockLLM([*fixture['start']['responses'], fixture['followup'], fixture['evaluation'], fixture['diagnosis'], fixture['teaching']])
    orchestrator = LearningOrchestrator(store, llm)
    diagnostic = await orchestrator.start(context, fixture['start']['goal'])
    followup = await orchestrator.answer(context, MultipleChoiceAnswer(question_id=diagnostic.question.question_id, selected_choice_id='a'))
    selection_not_mastery = store.read(context).active_topic.learning_state.mastery[0].status != 'mastered'
    teaching = await orchestrator.answer(context, TextAnswer(question_id=followup.question.question_id, text=fixture['reasoning']))
    topic = store.read(context).active_topic
    checks = {
        'selection_not_mastery': selection_not_mastery,
        'reasoning_outcome': topic.assessment_records[-1].assessment.outcome == fixture['outcome'],
        'misconception_evidence': topic.assessment_records[-1].diagnosis.misconceptions[0].evidence_quote in fixture['reasoning'],
        'contradiction_prevents_mastery': topic.learning_state.mastery[0].status == 'developing',
        'targeted_teaching': teaching.kind == 'explanation' and teaching.concept_id == followup.question.concept_id,
        'continuity': len(topic.history) == 2 and fixture['reasoning'] in topic.history[-1].user_text,
    }
    return {'scenario': fixture['name'], 'passed': all(checks.values()), 'checks': checks}


async def evaluate_continuity(fixture: dict) -> dict:
    from .context import ContextBudget, ContextBuilder
    from .conversation import ConversationTurn
    from .conversation_manager import ConversationManager
    from .learning import CompletionActivity
    context = RequestContext(request_id='evaluation', learner_id='fixture', session_id='fixture')
    store = InMemoryConversationStore()
    store.create(context)
    store.initialize_goal(context, 'Bubble Sort')
    store.append_turn(context, ConversationTurn(user_text='old ' * 1000, assistant_text='Earlier explanation'))
    store.append_turn(context, ConversationTurn(user_text='Recent question', assistant_text='Recent reply'))
    before = store.read(context)
    builder = ContextBuilder(ContextBudget(output_reserve=256, framing_allowance=128))
    mandatory = builder.build(before.active_topic.model_copy(update={'history': []}), 'Clarify that', 'Explain concisely.', CompletionActivity)
    # Reserve enough for the current schema and one small recent turn, but not the old oversized turn.
    builder = ContextBuilder(builder.budget.model_copy(update={'context_window': builder.estimated_tokens(mandatory, CompletionActivity) + 512}))
    messages = builder.build(before.active_topic, 'Clarify that', 'Explain concisely.', CompletionActivity)
    encoded = ' '.join(message.content for message in messages)
    mock = MockLLM(fixture['responses'])
    manager = ConversationManager(store, mock)
    await manager.send(context, 'Clarify adjacent comparisons.')
    continuity = 'Recent question' in ' '.join(message.content for message in mock.calls[1].messages)
    await manager.send(context, 'Switch to graph theory.')
    session = store.read(context)
    new_reply_context = ' '.join(message.content for message in mock.calls[-1].messages)
    checks = {
        'bounded_context': builder.estimated_tokens(messages, CompletionActivity) <= builder.budget.context_window,
        'newest_turn_preserved': 'Recent question' in encoded and 'old old old' not in encoded,
        'history_not_deleted': len(before.history) == 2,
        'conversation_continuity': continuity,
        'topic_isolation': session.active_topic.learning_state.goal == 'Graph theory' and 'Bubble Sort' not in new_reply_context,
        'archive_preserved': len(session.archived_topics[0].history) == 3 and len(session.history) == 4,
    }
    return {'scenario': fixture['name'], 'passed': all(checks.values()), 'checks': checks}


async def evaluate_memory(fixture: dict) -> dict:
    from tempfile import TemporaryDirectory
    from .conversation import SessionNotFoundError
    from .memory import LearnerScopedMemory
    from .orchestrator import LearningOrchestrator
    from .sqlite_memory import SQLiteLearningMemory
    first = RequestContext(request_id='evaluation', learner_id='first', session_id='shared')
    second = first.model_copy(update={'learner_id': 'second'})
    with TemporaryDirectory(prefix='athena-evaluation-') as directory:
        path = Path(directory) / 'memory.sqlite'
        with SQLiteLearningMemory(path) as store:
            bound = LearnerScopedMemory(store, first.learner_id)
            question = await LearningOrchestrator(bound, MockLLM(fixture['start']['responses'])).start(first, fixture['start']['goal'])
            other_question = await LearningOrchestrator(store, MockLLM(fixture['start']['responses'])).start(second, 'Other learner goal')
            other_before = store.read(second)
        with SQLiteLearningMemory(path) as store:
            bound = LearnerScopedMemory(store, first.learner_id)
            orchestrator = LearningOrchestrator(bound, MockLLM([fixture['followup']]))
            resumed = orchestrator.resume(first) == question
            blocked = False
            try:
                bound.read(second)
            except SessionNotFoundError:
                blocked = True
            answer = MultipleChoiceAnswer(question_id=question.question.question_id, selected_choice_id='a')
            activity = await orchestrator.answer(first, answer)
            saved = store.read(first)
            replay = await orchestrator.answer(first, answer)
            checks = {
                'resumed': resumed,
                'duplicate_result': replay == activity,
                'duplicate_no_write': store.read(first) == saved and len(saved.active_topic.assessment_records) == 1,
                'learner_binding': blocked,
                'same_session_isolated': store.read(second) == other_before and other_question.question.question_id != question.question.question_id,
            }
    return {'scenario': 'durable_memory_isolation', 'passed': all(checks.values()), 'checks': checks}


async def evaluate_source_safety(fixture: dict) -> dict:
    from .knowledge import KnowledgeService
    from .llm import LLMError
    from .reliable_llm import ReliableLLM, RetryPolicy
    context = RequestContext(request_id='evaluation', learner_id='fixture', session_id='fixture')
    store = InMemoryConversationStore()
    store.create(context)
    store.initialize_goal(context, 'Bubble Sort')
    session = store.read(context)
    session.active_topic.roadmap = Roadmap.model_validate({
        'goal': 'Bubble Sort', 'scope': {'scope': 'narrow', 'rationale': 'One algorithm'},
        'graph': {'partial_coverage': False, 'concepts': [{'concept_id': 'bubble-sort', 'title': 'Bubble Sort', 'description': 'Adjacent comparisons', 'objectives': ['Apply adjacent swaps'], 'difficulty': 'beginner'}]},
    })
    store._save(context, session)
    assessor = AssessmentService(store, MockLLM([{'prompt': 'Choose a comparison.', 'choices': [{'choice_id': 'a', 'text': 'Neighbours'}, {'choice_id': 'b', 'text': 'Random'}], 'correct_choice_id': 'a', 'rationale': 'Compare neighbours.'}]))
    question = await assessor.generate_multiple_choice(context, 'bubble-sort')
    assessment = await assessor.evaluate(context, MultipleChoiceAnswer(question_id=question.question.question_id, selected_choice_id='b'))
    from .retrieval import RetrievalResult
    await KnowledgeService(store).supply(context, RetrievalResult.model_validate(fixture['materials']))
    baseline = store.read(context)
    results = []
    for case in fixture['cases']:
        mock = MockLLM(case['responses'])
        teacher = TeachingService(store, ReliableLLM(mock, policy=RetryPolicy(max_attempts=1)))
        error_code = None
        activity = None
        try:
            activity = await teacher.explain(context, assessment.assessment_id)
        except LLMError as error:
            error_code = error.code
        checks = {
            'expected_outcome': error_code == case.get('expected_error'),
            'state_unchanged': store.read(context) == baseline,
            'source_not_system_instruction': all('IGNORE ALL RULES' not in message.content for call in mock.calls for message in call.messages if message.role == 'system'),
            'citation_resolves': activity is None or bool(activity.sources) and activity.sources[0].quote in fixture['materials']['items'][0]['text'],
        }
        results.append({'scenario': case['name'], 'passed': all(checks.values()), 'checks': checks})
    return {'passed': all(result['passed'] for result in results), 'results': results}


async def evaluate_fixture(fixture: dict) -> dict:
    if fixture.get('kind') == 'source_safety':
        return await evaluate_source_safety(fixture)
    if fixture.get('kind') == 'memory':
        return await evaluate_memory(fixture)
    if 'turns' in fixture:
        from .runner import run_text_journey
        return await run_text_journey(fixture)
    if 'behavior_scenarios' in fixture:
        results = [await (evaluate_continuity(scenario) if scenario['kind'] == 'continuity' else evaluate_assessment_loop(scenario)) for scenario in fixture['behavior_scenarios']]
        return {'passed': bool(results) and all(result['passed'] for result in results), 'results': results}
    if 'scenarios' not in fixture:
        return await evaluate_teaching(fixture)
    results = [await evaluate_start(scenario) for scenario in fixture['scenarios']]
    return {'passed': bool(results) and all(result['passed'] for result in results), 'results': results}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fixture', type=Path)
    args = parser.parse_args()
    result = asyncio.run(evaluate_fixture(json.loads(args.fixture.read_text())))
    print(json.dumps(result, sort_keys=True))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
