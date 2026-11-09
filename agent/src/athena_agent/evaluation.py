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
    builder = ContextBuilder(ContextBudget(context_window=2500, output_reserve=256, framing_allowance=128))
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


async def evaluate_fixture(fixture: dict) -> dict:
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
