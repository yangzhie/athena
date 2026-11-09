"""Capability-aware content descriptions; never renders or executes UI."""

from .activities import ActivitySelection, ClientCapabilities
from .context import ContextBuilder
from .contracts import RequestContext
from .conversation import ConversationError, InMemoryConversationStore
from .llm import LLM
from .memory import LearningMemoryStore
from .teaching import TeachingService


class ContentService:
    def __init__(self, store: LearningMemoryStore, llm: LLM, *, context_builder: ContextBuilder | None = None):
        self.store = store
        self.llm = llm
        self.context_builder = context_builder if context_builder is not None else ContextBuilder()

    async def set_capabilities(self, context: RequestContext, capabilities: ClientCapabilities) -> None:
        capabilities = ClientCapabilities.model_validate(capabilities.model_dump())
        async with self.store.interaction(context) as session:
            if session.capabilities != capabilities:
                session.capabilities = capabilities
                self.store._save(context, session)

    async def choose(self, context: RequestContext, concept_id: str) -> ActivitySelection:
        async with self.store.interaction(context) as session:
            topic = session.active_topic
            if topic is None or topic.roadmap is None or concept_id not in {item.concept_id for item in topic.roadmap.graph.concepts}:
                raise ConversationError('The concept is not in the active roadmap.')
            if not any(format != 'text' for format in session.capabilities.formats):
                return ActivitySelection(concept_id=concept_id, format='text', rationale='Text is available for this client.')
            staged = InMemoryConversationStore()
            staged.create(context, snapshot=session)
            recommendation = await TeachingService(staged, self.llm, context_builder=self.context_builder).recommend_format(context, concept_id)
            if self.store.read(context).revision != session.revision:
                raise ConversationError('The session changed; retry this interaction.')
            selected = recommendation.format if recommendation.format in session.capabilities.formats else 'text'
            return ActivitySelection(concept_id=concept_id, format=selected,
                                     rationale=recommendation.rationale if selected == recommendation.format else 'The recommended format is unsupported; use its text alternative.')
