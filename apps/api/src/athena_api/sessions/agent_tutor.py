"""The tutor backed by the adaptive learning agent in agent/, used in-process.

One learning session here = one agent session with the same id and the student's
goal. The agent's memory is scoped to the student (LearnerScopedMemory), and the
learner id comes from our server-side auth, never the client.
"""

import copy
import os
import uuid
from dataclasses import asdict
from pathlib import Path

from athena_agent.activities import ClientCapabilities
from athena_agent.context import ContextBudget, ContextBudgetError, ContextBuilder
from athena_agent.contracts import RequestContext
from athena_agent.learning import LearningActivity, MultipleChoiceAnswer, TextAnswer
from athena_agent.llm import LLM
from athena_agent.memory import LearnerScopedMemory, LearningMemoryStore
from athena_agent.orchestrator import LearningOrchestrator
from athena_agent.retrieval import RetrievalResult

from .material import MaterialProvider
from .models import LearningSession
from .operations import Operation
from .tutor import TutorError, TutorReply

#: The agent's context budget, in UTF-8 bytes (its cautious stand-in for tokens).
#: Its default (16 KiB) is too small once lecture transcripts are attached; ~128 KiB is
#: about 32k tokens, well within current models. ATHENA_AGENT_CONTEXT_BYTES overrides it.
DEFAULT_CONTEXT_BYTES = 131_072

#: Agent error codes → HTTP status. Messages shown to the student stay generic.
_STATUS = {
    "invalid_request": 400,
    "session_not_found": 404,
    "insufficient_evidence": 409,
    "conflicting_sources": 409,
    "invalid_model_output": 502,
    "dependency_unavailable": 503,
}


def activity_reply(activity: LearningActivity) -> TutorReply:
    """Turn an agent activity into a chat message. The activity JSON is learner-facing (no answers)."""
    data = activity.model_dump(mode="json")
    if activity.kind == "question":
        content = activity.question.prompt
    else:
        content = activity.text
    return TutorReply(
        content=content,
        sources=data.get("sources", []),
        knowledge_origin=data.get("knowledge_origin"),
        activity=data,
    )


class AgentTutor:
    mode = "ai"
    available = True

    def __init__(
        self,
        store: LearningMemoryStore,
        llm: LLM,
        *,
        capabilities: ClientCapabilities | None = None,
        material: MaterialProvider | None = None,
        context_bytes: int | None = None,
    ):
        self.store = store
        self.llm = llm
        #: Picks the unit's approved lecture clips for each session's goal.
        self.material = material
        self.profile_provider = None
        self.context_budget = ContextBudget(
            context_window=context_bytes or int(os.environ.get("ATHENA_AGENT_CONTEXT_BYTES", DEFAULT_CONTEXT_BYTES))
        )
        # The web app renders text for now; richer formats (diagrams, widgets) come later.
        self.capabilities = capabilities or ClientCapabilities(formats=["text"])

    def _context(self, session: LearningSession) -> RequestContext:
        return RequestContext(request_id=uuid.uuid4().hex, learner_id=session.student_id, session_id=session.id)

    def _orchestrator(self, session: LearningSession) -> LearningOrchestrator:
        return LearningOrchestrator(
            LearnerScopedMemory(self.store, session.student_id), self.llm,
            context_builder=ContextBuilder(self.context_budget),
        )

    async def _run(self, coro):
        try:
            return await coro
        except ContextBudgetError:
            raise TutorError(
                "This session has more material and history than the tutor can read at once. Start a new session "
                "for the next idea.", 413,
            ) from None
        except Exception as e:  # agent errors carry a code; anything else is a 500
            code = getattr(e, "code", None)
            if code is None:
                raise
            messages = {
                400: "That doesn't fit where this session is. Refresh and try again.",
                404: "The tutor lost track of this session.",
                409: "There isn't enough unit material to answer that reliably.",
                502: "The tutor gave an unusable answer. Try again.",
                503: "The tutor is unavailable right now. Try again later.",
            }
            status = _STATUS.get(code, 500)
            message = messages.get(status, "The tutor couldn't complete that.")
            if code == 'conflicting_sources':
                message = "Your unit sources conflict. Resolve the conflicting material before retrying this learning step."
            raise TutorError(message, status, code=code) from None

    async def operation(self, operation: Operation) -> list[TutorReply]:
        return await self._run(self._operation(operation))

    async def _operation(self, operation: Operation) -> list[TutorReply]:
        """Publish an agent transition and its replay result in the same snapshot.

        Model calls run against an isolated copy. A failed host write can replay
        this private receipt after restart without repeating the transition.
        """
        from athena_agent.conversation import InMemoryConversationStore, SessionNotFoundError, ConversationError

        session = operation.session
        context = self._context(session)
        try:
            original = self.store.read(context)
        except SessionNotFoundError:
            original = None
        signature = {"kind": operation.kind, "payload": operation.payload}

        def replay(snapshot):
            receipt = snapshot.operation_results.get(operation.id) if snapshot else None
            if receipt is None:
                return None
            if receipt["request"] != signature:
                raise TutorError("Operation identifier already used for a different request.", 409)
            return [TutorReply(**r) for r in receipt["replies"]]

        previous = replay(original)
        if previous is not None:
            return previous
        staged = InMemoryConversationStore()
        if original:
            staged.create(context, snapshot=original)
        worker = copy.copy(self)
        worker.store = staged
        if self.profile_provider and self.mode == 'ai':
            from ..learning.service import LearnerAwareLLM
            profile = self.profile_provider(session.student_id)
            if profile:
                worker.llm = LearnerAwareLLM(self.llm, profile)
        if original and original.active_topic and self.material is not None:
            from athena_agent.knowledge import KnowledgeService
            topic = original.active_topic
            query = topic.learning_state.goal
            if topic.roadmap:
                concept = next((c for c in topic.roadmap.graph.concepts if c.concept_id == topic.learning_state.current_concept_id), None)
                if concept:
                    query += ' ' + concept.title
            if operation.kind == 'message':
                query += ' ' + operation.payload['text'][:300]
            items = self.material.for_goal(session.offering_id, query)
            knowledge = KnowledgeService(LearnerScopedMemory(staged, session.student_id))
            if items:
                await knowledge.supply(context, RetrievalResult.model_validate({'items': items}))
            else:
                # A successful empty retrieval means explicitly labelled general knowledge.
                await knowledge.use_general_knowledge(context)
        if operation.kind == "start":
            replies = await worker.start(session)
        elif operation.kind == "message":
            replies = await worker.message(session, **operation.payload)
        elif operation.kind == "answer":
            replies = await worker.answer(session, **operation.payload)
        elif operation.kind == "continue":
            replies = await worker.continue_(session, **operation.payload)
        else:
            raise TutorError("Unknown tutor operation.", 400)
        snapshot = staged.read(context)
        snapshot.operation_results[operation.id] = {"request": signature, "replies": [asdict(r) for r in replies]}
        try:
            if original is None:
                self.store.create(context, snapshot=snapshot)
            else:
                snapshot.revision = original.revision
                self.store._save(context, snapshot)
        except ConversationError as error:
            if error.code != "invalid_request":
                raise
            # An independent adapter may have won the compare-and-save race.
            accepted = replay(self.store.read(context))
            if accepted is not None:
                return accepted
            raise TutorError("The session changed. Retry this operation.", 409) from None
        return replies

    def materials_for(self, session: LearningSession) -> RetrievalResult | None:
        items = self.material.for_goal(session.offering_id, session.goal) if self.material else []
        return RetrievalResult.model_validate({"items": items}) if items else None

    async def start(self, session: LearningSession) -> list[TutorReply]:
        """Start the agent with the goal and, as grounding, the unit's best-matching approved clips.

        If the agent finds those clips don't cover the goal, start without them: the
        agent then teaches from general knowledge and labels its answers that way.
        """
        materials = self.materials_for(session)
        try:
            activity = await self._run(
                self._orchestrator(session).start(
                    self._context(session), session.goal, materials=materials, capabilities=self.capabilities,
                )
            )
        except TutorError as e:
            if materials is None or e.code != "insufficient_evidence":
                raise
            activity = await self._run(
                self._orchestrator(session).start(self._context(session), session.goal, capabilities=self.capabilities)
            )
        return [activity_reply(activity)]

    async def message(self, session: LearningSession, text: str) -> list[TutorReply]:
        result = await self._run(self._orchestrator(session).message(self._context(session), text))
        replies = [TutorReply(result.reply.text)]
        if result.activity is not None:
            replies.append(activity_reply(result.activity))
        return replies

    async def answer(self, session, question_id, *, choice_id, text, hint_used=False) -> list[TutorReply]:
        if choice_id is not None:
            answer = MultipleChoiceAnswer(question_id=question_id, selected_choice_id=choice_id)
        elif text is not None and text.strip():
            answer = TextAnswer(question_id=question_id, text=text.strip())
        else:
            raise TutorError("An answer is required.", 400)
        activity = await self._run(
            self._orchestrator(session).answer(self._context(session), answer, hint_used=hint_used)
        )
        return [activity_reply(activity)]

    async def continue_(self, session: LearningSession, activity_id: str) -> list[TutorReply]:
        activity = await self._run(self._orchestrator(session).continue_learning(self._context(session), activity_id))
        return [activity_reply(activity)]


def agent_tutor_from_env(material: MaterialProvider | None = None):
    """Configured AI by default; offline/placeholder modes require explicit selection."""
    from .tutor import PlaceholderTutor, UnavailableTutor

    mode = os.environ.get("ATHENA_TUTOR", "ai").strip().lower() or "ai"
    if mode == "placeholder":
        return PlaceholderTutor()
    if mode == "demo":
        fixture = Path(__file__).resolve().parents[5] / "agent/tests/fixtures/api_journey.json"
        try:
            return ScriptedDemoTutor(fixture)
        except (OSError, ValueError):
            return UnavailableTutor("The scripted demo fixture is unavailable.")
    if mode != "ai":
        return UnavailableTutor("Unknown ATHENA_TUTOR mode.")
    from athena_agent.llm import LLMError
    from athena_agent.openai_llm import OpenAILLM, OpenAISettings
    from athena_agent.reliable_llm import ReliableLLM
    from athena_agent.sqlite_memory import SQLiteLearningMemory

    try:
        llm = ReliableLLM(OpenAILLM(OpenAISettings.from_env()))
    except LLMError:
        return UnavailableTutor("Configure OPENAI_API_KEY and OPENAI_MODEL for the AI tutor.")
    path = Path(os.environ.get("ATHENA_AGENT_DB", "data/agent.db"))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        return AgentTutor(SQLiteLearningMemory(path), llm, material=material)
    except Exception:
        return UnavailableTutor("Tutor storage is unavailable.")


class ScriptedDemoTutor(AgentTutor):
    """ATHENA_TUTOR=demo, for trying the UI without OpenAI.

    Every new session replays the agent's own scripted journey
    (agent/tests/fixtures/api_journey.json): real orchestration, canned model output.
    The content is that script's (a synthetic Bubble Sort lesson) whatever goal is typed,
    and agent state is in memory, so it's lost when the API restarts.
    """

    mode = "demo"

    def __init__(self, fixture_path: Path):
        import json

        from athena_agent.conversation import InMemoryConversationStore

        self.fixture = json.loads(fixture_path.read_text())
        self._llms: dict[str, LLM] = {}
        super().__init__(InMemoryConversationStore(), llm=None)  # type: ignore[arg-type]

    def _orchestrator(self, session: LearningSession) -> LearningOrchestrator:
        from athena_agent.llm import MockLLM
        from athena_agent.reliable_llm import ReliableLLM, RetryPolicy

        llm = self._llms.setdefault(
            session.id, ReliableLLM(MockLLM(self.fixture["responses"]), policy=RetryPolicy(max_attempts=1))
        )
        return LearningOrchestrator(
            LearnerScopedMemory(self.store, session.student_id), llm, context_builder=ContextBuilder(self.context_budget)
        )

    async def start(self, session: LearningSession) -> list[TutorReply]:
        from athena_agent.knowledge import KnowledgeService
        from athena_agent.retrieval import MockRetriever

        activity = await self._run(
            self._orchestrator(session).start(self._context(session), session.goal, capabilities=self.capabilities)
        )
        opening = activity_reply(activity)
        opening.content = "Scripted demo: synthetic Bubble Sort fixture; state is lost on restart.\n\n" + opening.content
        replies = [opening]
        # The script expects its materials to be selected right after the start.
        memory = LearnerScopedMemory(self.store, session.student_id)
        await KnowledgeService(memory, MockRetriever([self.fixture["materials"]])).retrieve(
            self._context(session), self.fixture["goal"]
        )
        return replies
