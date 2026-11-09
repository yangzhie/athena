"""Local scripted text journeys over mock dependencies; never calls live models."""

import argparse
import asyncio
import json
from pathlib import Path

from .contracts import RequestContext
from .conversation import InMemoryConversationStore
from .learning import MultipleChoiceAnswer, QuestionActivity, TextAnswer
from .llm import MockLLM
from .orchestrator import LearningOrchestrator


async def run_text_journey(fixture: dict) -> dict:
    context = RequestContext(request_id='runner', learner_id='local-fixture', session_id='local-fixture')
    store = InMemoryConversationStore()
    mock = MockLLM(fixture['responses'])
    orchestrator = LearningOrchestrator(store, mock)
    activity = await orchestrator.start(context, fixture['goal'])
    transcript = []

    def snapshot():
        state = store.read(context).active_topic.learning_state
        transcript.append({
            'kind': activity.kind,
            'text': activity.question.prompt if isinstance(activity, QuestionActivity) else activity.text,
            'phase': state.phase,
            'concept_id': getattr(activity, 'concept_id', activity.question.concept_id if isinstance(activity, QuestionActivity) else None),
            'mastered': sum(item.status == 'mastered' for item in state.mastery),
        })

    snapshot()
    for turn in fixture['turns']:
        if turn['kind'] == 'continue':
            activity = await orchestrator.continue_learning(context, activity.activity_id)
        elif isinstance(activity, QuestionActivity):
            if turn['kind'] == 'choice':
                answer = MultipleChoiceAnswer(question_id=activity.question.question_id, selected_choice_id=turn['value'])
            elif turn['kind'] == 'text':
                answer = TextAnswer(question_id=activity.question.question_id, text=turn['value'])
            else:
                raise ValueError('Unsupported scripted turn.')
            activity = await orchestrator.answer(context, answer)
        else:
            raise ValueError('A scripted answer requires a question.')
        snapshot()
    checks = {
        'phases': [item['phase'] for item in transcript] == fixture['expected_phases'],
        'mastery_progress': [item['mastered'] for item in transcript] == fixture['expected_mastered'],
        'targeted_teaching': all(item['concept_id'] == fixture['concept_id'] for item in transcript if item['kind'] == 'explanation'),
        'concise_teaching': all(len(item['text'].split()) <= 120 and len(item['text']) <= 1000 for item in transcript if item['kind'] == 'explanation'),
        'completion': activity.kind == 'completion' and store.read(context).active_topic.learning_state.phase == 'complete',
    }
    return {'scenario': fixture['name'], 'passed': all(checks.values()), 'checks': checks, 'transcript': transcript}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fixture', type=Path)
    args = parser.parse_args()
    result = asyncio.run(run_text_journey(json.loads(args.fixture.read_text())))
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
