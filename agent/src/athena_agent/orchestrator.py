"""Backend learning actions composed from existing planning/assessment services."""

from pydantic import TypeAdapter

from .assessment import AssessmentService
from .context import ContextBuilder
from .contracts import RequestContext
from .conversation import ConversationError, InMemoryConversationStore
from .learning import Difficulty, QuestionActivity
from .llm import LLM
from .planning import PlanningService
from .reliable_llm import ReliableLLM


class LearningOrchestrator:
    def __init__(self, store: InMemoryConversationStore, llm: LLM, *, context_builder: ContextBuilder | None = None):
        self.store = store
        self.llm = llm if isinstance(llm, ReliableLLM) else ReliableLLM(llm)
        self.context_builder = context_builder if context_builder is not None else ContextBuilder()

    async def start(self, context: RequestContext, goal: str, *, difficulty: Difficulty = 'beginner') -> QuestionActivity:
        """Start a resolved goal with a proactive diagnostic, publishing all or nothing."""
        difficulty = TypeAdapter(Difficulty).validate_python(difficulty)
        async with self.store.creation(context):
            staged = InMemoryConversationStore()
            staged.create(context)
            staged.initialize_goal(context, goal)
            roadmap = await PlanningService(self.llm, store=staged, context_builder=self.context_builder).plan(context)
            state = staged.read(context).active_topic.learning_state
            eligible = roadmap.eligible_concept_ids(state)
            if not eligible:
                raise ConversationError('The roadmap has no eligible diagnostic concept.')
            activity = await AssessmentService(staged, self.llm, context_builder=self.context_builder).generate_multiple_choice(context, eligible[0], difficulty=difficulty)
            session = staged.read(context)
            session.active_topic.current_activity = activity
            session.active_topic.learning_state.current_concept_id = activity.question.concept_id
            staged._save(context, session)
            self.store.create(context, snapshot=staged.read(context))
            return activity.model_copy(deep=True)
