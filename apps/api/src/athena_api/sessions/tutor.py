"""Who writes the tutor's messages: the agent (agent/), or a placeholder without it."""

from dataclasses import dataclass, field
from typing import Literal, Protocol

from .models import LearningSession


@dataclass
class TutorReply:
    content: str
    sources: list[dict] = field(default_factory=list)
    knowledge_origin: Literal["materials", "supplement", "general"] | None = None
    #: The agent activity behind this message (question, explanation, feedback, ...).
    activity: dict | None = None


class TutorError(RuntimeError):
    """The tutor couldn't do it. `status` is the HTTP status to report."""

    def __init__(self, message: str, status: int = 503):
        super().__init__(message)
        self.status = status


class Tutor(Protocol):
    async def start(self, session: LearningSession) -> list[TutorReply]:
        """Open the session. The tutor asks first (a diagnostic question), not the learner."""
        ...

    async def message(self, session: LearningSession, text: str) -> list[TutorReply]:
        """A free-text chat message (clarification, follow-up, question)."""
        ...

    async def answer(self, session: LearningSession, question_id: str, *, choice_id: str | None, text: str | None,
                     hint_used: bool = False) -> list[TutorReply]:
        """An answer to a question the tutor asked."""
        ...

    async def continue_(self, session: LearningSession, activity_id: str) -> list[TutorReply]:
        """Move on after a teaching step."""
        ...


class PlaceholderTutor:
    """Explicitly selected canned replies; never a configuration fallback."""

    mode = "placeholder"
    available = True

    async def start(self, session: LearningSession) -> list[TutorReply]:
        return [TutorReply(
            "Placeholder tutor (canned replies).\n\n"
            f"Let’s work on “{session.goal}”. To start, tell me what you already know about it, "
            "or where you get stuck. I’ll pitch things from there."
        )]

    async def message(self, session: LearningSession, text: str) -> list[TutorReply]:
        return [TutorReply(
            "This is a placeholder reply, because the tutor isn’t connected.\n\n"
            f"You said: “{text}”\n\n"
            "With the agent running (OpenAI configured), I’ll diagnose what you know, teach "
            f"“{session.goal}” step by step, check your understanding with questions, and cite your unit’s material."
        )]

    async def answer(self, session, question_id, *, choice_id, text, hint_used=False):
        raise TutorError("The placeholder tutor doesn't ask questions.", 400)

    async def continue_(self, session, activity_id):
        raise TutorError("The placeholder tutor doesn't teach in steps.", 400)


class UnavailableTutor:
    mode = "unavailable"
    available = False

    def __init__(self, reason: str):
        self.reason = reason

    async def start(self, *_args, **_kwargs):
        raise TutorError(f"The AI tutor is unavailable. {self.reason}", 503)

    message = start
    answer = start
    continue_ = start
