"""Client request bodies deliberately exclude trusted learner identity."""

from ._schema import Contract, NonBlankString
from .learning import Difficulty


class StartSession(Contract):
    session_id: NonBlankString
    goal: NonBlankString
    difficulty: Difficulty = 'beginner'
