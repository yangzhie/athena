"""The tutor backed by the adaptive learning agent in agent/, used in-process.

One learning session here = one agent session with the same id and the student's
goal. The agent's memory is scoped to the student (LearnerScopedMemory), and the
learner id comes from our server-side auth, never the client.
"""

import os
import uuid
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
            raise TutorError(messages.get(status, "The tutor couldn't complete that."), status) from None

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
            if materials is None or e.status != 409:
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


def agent_tutor_from_env(material: MaterialProvider | None = None) -> AgentTutor | None:
    """The agent with OpenAI and durable memory, if configured; else None.

    ATHENA_TUTOR=placeholder forces the placeholder (e.g. while there are no API credits);
    ATHENA_TUTOR=demo replays the agent's scripted journey (no OpenAI needed).
    The agent keeps its memory in its own database (ATHENA_AGENT_DB, default data/agent.db):
    its tables must not share a file with ours.
    """
    mode = os.environ.get("ATHENA_TUTOR", "").strip().lower()
    if mode == "placeholder":
        return None
    if mode == "demo":
        fixture = Path(__file__).resolve().parents[5] / "agent/tests/fixtures/api_journey.json"
        return ScriptedDemoTutor(fixture)
    from athena_agent.llm import LLMError
    from athena_agent.openai_llm import OpenAILLM, OpenAISettings
    from athena_agent.reliable_llm import ReliableLLM
    from athena_agent.sqlite_memory import SQLiteLearningMemory

    try:
        llm = ReliableLLM(OpenAILLM(OpenAISettings.from_env()))
    except LLMError:
        return None
    path = Path(os.environ.get("ATHENA_AGENT_DB", "data/agent.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return AgentTutor(SQLiteLearningMemory(path), llm, material=material)


class ScriptedDemoTutor(AgentTutor):
    """ATHENA_TUTOR=demo, for trying the UI without OpenAI.

    Every new session replays the agent's own scripted journey
    (agent/tests/fixtures/api_journey.json): real orchestration, canned model output.
    The content is that script's (a synthetic Bubble Sort lesson) whatever goal is typed,
    and agent state is in memory, so it's lost when the API restarts.
    """

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
        replies = [activity_reply(activity)]
        # The script expects its materials to be selected right after the start.
        memory = LearnerScopedMemory(self.store, session.student_id)
        await KnowledgeService(memory, MockRetriever([self.fixture["materials"]])).retrieve(
            self._context(session), self.fixture["goal"]
        )
        return replies
