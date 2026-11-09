"""Conservative presentation/difficulty adaptation; never changes mastery."""

from typing import TYPE_CHECKING, Literal

from ._schema import Contract
from .conversation import ConversationError
from .learning import Difficulty

if TYPE_CHECKING:
    from .conversation import TopicContext


class LearningAdjustment(Contract):
    difficulty: Difficulty
    depth: Literal['concise', 'scaffolded']
    pacing: Literal['one_unit', 'application']


def adjust_learning(topic: 'TopicContext', concept_id: str) -> LearningAdjustment:
    concept = next((item for item in topic.roadmap.graph.concepts if item.concept_id == concept_id), None) if topic.roadmap else None
    if concept is None:
        raise ConversationError('The concept is not in the active roadmap.')
    decisive = [item for item in topic.assessment_records if item.assessment.concept_id == concept_id and item.assessment.outcome != 'uncertain' and item.assessment.confidence >= 0.8]
    failures = successes = 0
    for record in reversed(decisive):
        if record.assessment.outcome == 'correct':
            if failures or record.hint_used:
                break
            successes += 1
        else:
            if successes:
                break
            failures += 1
    levels = ['beginner', 'intermediate', 'advanced']
    index = levels.index(concept.difficulty)
    if failures >= 2:
        index = max(0, index - 1)
    elif successes >= 2:
        index = min(2, index + 1)
    return LearningAdjustment(difficulty=levels[index], depth='scaffolded' if failures >= 2 else 'concise', pacing='application' if successes else 'one_unit')
