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


async def evaluate_fixture(fixture: dict) -> dict:
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
