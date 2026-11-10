"""OpenAI Responses adapter with explicit configuration and no internal retries."""

import os
from typing import Annotated, Self, Sequence

from openai import (
    APIConnectionError, APIResponseValidationError, APIStatusError,
    AsyncOpenAI, OpenAIError,
)
from pydantic import Field, SecretStr, ValidationError

from ._schema import Contract, NonBlankString
from .llm import DependencyError, InvalidOutputError, Message, Model, ModelRefusalError


class OpenAISettings(Contract):
    model: NonBlankString
    api_key: SecretStr | None = Field(default=None, repr=False, exclude=True)
    timeout: Annotated[float, Field(gt=0, allow_inf_nan=False)] = 30.0
    max_output_tokens: Annotated[int, Field(gt=0)] = 2048

    @classmethod
    def from_env(cls) -> Self:
        model = os.environ.get('OPENAI_MODEL')
        if not model or not model.strip():
            raise DependencyError('Configure OPENAI_MODEL before using the live adapter.')
        key = os.environ.get('OPENAI_API_KEY')
        return cls(model=model, api_key=SecretStr(key) if key else None)


class OpenAILLM:
    """Owns its SDK client unless a caller injects one (for tests or shared use)."""

    def __init__(self, settings: OpenAISettings, *, client: AsyncOpenAI | None = None):
        self.settings = settings.model_copy(deep=True)
        self.usage: list[dict[str, int]] = []
        self._owns_client = client is None
        if client is None:
            key = settings.api_key.get_secret_value() if settings.api_key else ''
            if not key.strip():
                raise DependencyError('Configure OPENAI_API_KEY before using the live adapter.')
            client = AsyncOpenAI(api_key=key, max_retries=0, timeout=settings.timeout)
        # Also disable retries for injected clients; never close the caller's client.
        self._client = client.with_options(max_retries=0, timeout=settings.timeout)
        self._owned_client = client

    async def generate(self, messages: Sequence[Message], response_model: type[Model]) -> Model:
        try:
            response = await self._client.responses.parse(
                model=self.settings.model,
                input=[message.model_dump() for message in messages],
                text_format=response_model,
                max_output_tokens=self.settings.max_output_tokens,
                store=False,
            )
        except (ValidationError, APIResponseValidationError):
            raise InvalidOutputError() from None
        except APIConnectionError:
            raise DependencyError('The model service is temporarily unavailable.', retryable=True) from None
        except APIStatusError as error:
            retryable = error.status_code in {408, 409, 429} or error.status_code >= 500
            raise DependencyError('The model service could not complete this request.', retryable=retryable) from None
        except OpenAIError:
            raise DependencyError('The model service could not complete this request.') from None

        if getattr(response, 'usage', None):
            self.usage.append({'input_tokens': response.usage.input_tokens, 'output_tokens': response.usage.output_tokens, 'cached_input_tokens': getattr(response.usage.input_tokens_details, 'cached_tokens', 0)})
        for item in response.output:
            if item.type == 'message':
                for content in item.content:
                    if content.type == 'refusal':
                        raise ModelRefusalError()
        if response.status != 'completed':
            raise DependencyError('The model response did not complete.')
        if response.output_parsed is None:
            raise InvalidOutputError()
        return response.output_parsed

    async def aclose(self) -> None:
        if self._owns_client:
            await self._owned_client.close()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_args) -> None:
        await self.aclose()
