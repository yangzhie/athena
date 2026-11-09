"""Provider-independent structured generation and deterministic test doubles."""

from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from typing import Literal, Protocol, Sequence, TypeVar

from pydantic import BaseModel, ValidationError

from ._schema import Contract, NonBlankString
from .contracts import ErrorCode

Model = TypeVar('Model', bound=BaseModel)


class Message(Contract):
    role: Literal['system', 'developer', 'user', 'assistant']
    content: NonBlankString


class LLMError(Exception):
    """Safe public failure; never embed provider bodies or prompts in messages."""

    code: ErrorCode = 'internal_error'

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class DependencyError(LLMError):
    code: ErrorCode = 'dependency_unavailable'


class InvalidOutputError(LLMError):
    code: ErrorCode = 'invalid_model_output'

    def __init__(self):
        super().__init__('The model returned an invalid structured response.', retryable=True)


class ModelRefusalError(LLMError):
    code: ErrorCode = 'invalid_model_output'

    def __init__(self):
        super().__init__('The model declined this request.')


class LLM(Protocol):
    async def generate(self, messages: Sequence[Message], response_model: type[Model]) -> Model:
        """Generate one instance of the supplied concrete Pydantic model."""
        ...


@dataclass(frozen=True)
class GenerationCall:
    messages: tuple[Message, ...]
    response_model: type[BaseModel]


class MockLLM:
    """Consume scripted responses/failures; no network or random fallback."""

    def __init__(self, responses: Sequence[BaseModel | dict | str | LLMError]):
        self._responses = deque(
            response if isinstance(response, LLMError) else deepcopy(response)
            for response in responses
        )
        self.calls: list[GenerationCall] = []

    async def generate(self, messages: Sequence[Message], response_model: type[Model]) -> Model:
        self.calls.append(GenerationCall(
            tuple(message.model_copy(deep=True) for message in messages), response_model,
        ))
        if not self._responses:
            raise DependencyError('No scripted model responses remain.')
        response = self._responses.popleft()
        if isinstance(response, LLMError):
            raise response
        try:
            if isinstance(response, BaseModel):
                response = response.model_dump(mode='python')
            if isinstance(response, str):
                return response_model.model_validate_json(response)
            return response_model.model_validate(response)
        except ValidationError:
            raise InvalidOutputError() from None
