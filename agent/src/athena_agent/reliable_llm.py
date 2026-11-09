"""Provider-independent output validation and bounded asynchronous retries."""

import asyncio
from typing import Annotated, Awaitable, Callable, Sequence

from pydantic import Field, ValidationError

from ._schema import Contract
from .llm import (
    LLM, DependencyError, InvalidOutputError, LLMError, Message, Model, ModelRefusalError,
)


class RetryPolicy(Contract):
    max_attempts: Annotated[int, Field(ge=1)] = 3
    initial_delay: Annotated[float, Field(ge=0, allow_inf_nan=False)] = 0.5
    max_delay: Annotated[float, Field(ge=0, allow_inf_nan=False)] = 30.0


def _safe_failure(error: Exception) -> LLMError:
    if isinstance(error, ModelRefusalError):
        return ModelRefusalError()
    if isinstance(error, (InvalidOutputError, ValidationError)):
        return InvalidOutputError()
    if isinstance(error, DependencyError):
        return DependencyError('The model service could not complete this request.', retryable=error.retryable)
    return LLMError('Model generation failed.')


class ReliableLLM:
    """Validate every returned model and retry only classified transient failures."""

    def __init__(
        self, llm: LLM, *, policy: RetryPolicy | None = None,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._llm = llm
        self.policy = (policy or RetryPolicy()).model_copy(deep=True)
        self._sleep = sleeper

    async def generate(self, messages: Sequence[Message], response_model: type[Model]) -> Model:
        snapshot = tuple(message.model_copy(deep=True) for message in messages)
        delay = min(self.policy.initial_delay, self.policy.max_delay)
        for attempt in range(self.policy.max_attempts):
            try:
                result = await self._llm.generate(
                    [message.model_copy(deep=True) for message in snapshot], response_model,
                )
                if not isinstance(result, response_model):
                    raise InvalidOutputError()
                # Dump and revalidate: Pydantic may otherwise trust an already-created
                # instance, including one bypassing validators via model_construct().
                return response_model.model_validate(result.model_dump(mode='python'))
            except Exception as error:
                failure = _safe_failure(error)
            if not failure.retryable or attempt + 1 == self.policy.max_attempts:
                raise failure from None
            await self._sleep(delay)
            delay = min(delay * 2, self.policy.max_delay)
        raise AssertionError('RetryPolicy requires at least one attempt.')
