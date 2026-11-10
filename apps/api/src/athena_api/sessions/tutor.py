"""Who writes the tutor's messages. A placeholder until the agent (agent/) is wired in."""

from dataclasses import dataclass, field
from typing import Literal, Protocol

from .models import LearningSession, Message


@dataclass
class TutorReply:
    content: str
    sources: list[dict] = field(default_factory=list)
    knowledge_origin: Literal["materials", "supplement", "general"] | None = None


class Tutor(Protocol):
    def opening(self, session: LearningSession) -> TutorReply:
        """The tutor's first message: it asks first rather than waiting for a question."""
        ...

    def reply(self, session: LearningSession, history: list[Message]) -> TutorReply:
        """Reply to the latest learner message in `history`."""
        ...


class PlaceholderTutor:
    def opening(self, session: LearningSession) -> TutorReply:
        return TutorReply(
            f"Let’s work on “{session.goal}”. To start, tell me what you already know about it, "
            "or where you get stuck. I’ll pitch things from there."
        )

    def reply(self, session: LearningSession, history: list[Message]) -> TutorReply:
        question = history[-1].content if history else ""
        return TutorReply(
            "This is a placeholder reply, because the tutor isn’t connected yet.\n\n"
            f"You said: “{question}”\n\n"
            f"Once the agent is wired in, I’ll teach “{session.goal}” step by step from your unit’s "
            "material, check your understanding with questions, and cite the slides and lecture clips I use."
        )
