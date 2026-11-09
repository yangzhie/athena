"""Backend learning actions composed from existing planning/assessment services."""

from uuid import uuid4

from pydantic import TypeAdapter

from .adaptation import adjust_learning
from .assessment import AssessmentService
from .assessment_models import AnswerSubmission
from .context import ContextBuilder
from .contracts import RequestContext
from .memory import LearningMemoryStore
from .decisions import LearningDecision, select_action
from .conversation import ConversationError, ConversationSession, ConversationTurn, InMemoryConversationStore
from .learning import Answer, CompletionActivity, Difficulty, ExplanationActivity, LearningActivity, QuestionActivity
from .llm import LLM, InvalidOutputError
from .planning import PlanningService
from .reliable_llm import ReliableLLM
from .teaching import TeachingService


class LearningOrchestrator:
    def __init__(self, store: LearningMemoryStore, llm: LLM, *, context_builder: ContextBuilder | None = None):
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


    def _stage(self, context: RequestContext, session: ConversationSession) -> InMemoryConversationStore:
        staged = InMemoryConversationStore()
        staged.create(context, snapshot=session)
        return staged

    def _publish(self, context: RequestContext, original: ConversationSession, staged: InMemoryConversationStore) -> None:
        updated = staged.read(context)
        updated.revision = original.revision
        self.store._save(context, updated)

    def _set_activity(self, context: RequestContext, staged: InMemoryConversationStore, activity: LearningActivity, phase: str) -> None:
        session = staged.read(context)
        topic = session.active_topic
        topic.current_activity = activity.model_copy(deep=True)
        topic.learning_state.phase = phase
        if isinstance(activity, QuestionActivity):
            topic.learning_state.current_concept_id = activity.question.concept_id
        elif phase == 'complete':
            topic.learning_state.current_concept_id = None
        staged._save(context, session)

    async def answer(self, context: RequestContext, answer: Answer, *, hint_used: bool = False) -> LearningActivity:
        submission = AnswerSubmission.model_validate({'answer': answer.model_dump() if hasattr(answer, 'model_dump') else answer, 'hint_used': hint_used})
        async with self.store.interaction(context) as original:
            topic = original.active_topic
            if topic is None or topic.roadmap is None:
                raise ConversationError('An active learning roadmap is required.')
            previous = next((item for item in topic.assessment_records if item.answer.question_id == submission.answer.question_id), None)
            if previous is not None and previous.next_activity is not None:
                if previous.answer != submission.answer or previous.hint_used != hint_used:
                    raise ConversationError('This question already has an answer; request a fresh question.')
                return previous.next_activity.model_copy(deep=True)
            if not isinstance(topic.current_activity, QuestionActivity) or topic.current_activity.question.question_id != submission.answer.question_id:
                raise ConversationError('Submit an answer to the current question.')
            staged = self._stage(context, original)
            assessor = AssessmentService(staged, self.llm, context_builder=self.context_builder)
            assessment = await assessor.evaluate(context, submission.answer, hint_used=hint_used)
            if assessment.outcome != 'correct':
                await assessor.diagnose(context, assessment.assessment_id)
            decision = select_action(staged.read(context).active_topic, assessment.assessment_id)
            if decision.action in {'teach', 'recover'}:
                teacher = TeachingService(staged, self.llm, context_builder=self.context_builder)
                activity = await (teacher.example(context, assessment.assessment_id) if decision.action == 'recover' else teacher.explain(context, assessment.assessment_id))
                phase = 'teach'
            elif decision.action == 'verify':
                activity = await assessor.generate_followup(context, assessment.assessment_id, difficulty=decision.difficulty)
                phase = 'reinforce'
            elif decision.action == 'diagnose':
                activity = await assessor.generate_multiple_choice(context, decision.concept_id, difficulty=decision.difficulty)
                phase = 'diagnose'
            else:
                roadmap = staged.read(context).active_topic.roadmap
                if roadmap.scope.scope == 'narrow' and not roadmap.graph.partial_coverage:
                    activity = CompletionActivity(activity_id=str(uuid4()), text='You have demonstrated understanding of this topic through independent assessment evidence.')
                    phase = 'complete'
                else:
                    revised = await PlanningService(self.llm, store=staged, context_builder=self.context_builder).revise(context)
                    if revised.scope.scope != roadmap.scope.scope or (roadmap.scope.scope == 'broad' and not revised.graph.partial_coverage):
                        raise InvalidOutputError()
                    eligible = revised.eligible_concept_ids(staged.read(context).active_topic.learning_state)
                    if not eligible:
                        raise InvalidOutputError()
                    activity = await assessor.generate_multiple_choice(context, eligible[0])
                    phase = 'diagnose'
            self._set_activity(context, staged, activity, phase)
            session = staged.read(context)
            record = next(item for item in session.active_topic.assessment_records if item.assessment.assessment_id == assessment.assessment_id)
            record.next_activity = activity.model_copy(deep=True)
            staged._save(context, session)
            user_text = submission.answer.text if submission.answer.kind == 'text' else submission.answer.selected_choice_id
            assistant_text = activity.question.prompt if isinstance(activity, QuestionActivity) else activity.text
            staged.append_turn(context, ConversationTurn(user_text=user_text, assistant_text=assistant_text))
            self._publish(context, original, staged)
            return activity.model_copy(deep=True)

    async def continue_learning(self, context: RequestContext, activity_id: str) -> QuestionActivity:
        """After a teaching unit, proactively ask an application question."""
        async with self.store.interaction(context) as original:
            topic = original.active_topic
            if topic is None or not isinstance(topic.current_activity, ExplanationActivity) or topic.current_activity.activity_id != activity_id:
                raise ConversationError('Continue the current teaching activity.')
            parent = next((item for item in topic.assessment_records if item.next_activity is not None and item.next_activity.activity_id == activity_id), None)
            if parent is None:
                raise ConversationError('The teaching activity has no assessment evidence.')
            staged = self._stage(context, original)
            activity = await AssessmentService(staged, self.llm, context_builder=self.context_builder).generate_followup(context, parent.assessment.assessment_id, purpose='application', difficulty=adjust_learning(topic, parent.assessment.concept_id).difficulty)
            self._set_activity(context, staged, activity, 'reinforce')
            self._publish(context, original, staged)
            return activity.model_copy(deep=True)


    def next_action(self, context: RequestContext, assessment_id: str) -> LearningDecision:
        topic = self.store.read(context).active_topic
        if topic is None:
            raise ConversationError('An active learning roadmap is required.')
        return select_action(topic, assessment_id)


    def resume(self, context: RequestContext) -> LearningActivity:
        topic = self.store.read(context).active_topic
        if topic is None or topic.current_activity is None:
            raise ConversationError('The session has no current learning activity.')
        return topic.current_activity.model_copy(deep=True)
