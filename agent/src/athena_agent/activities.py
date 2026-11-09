"""Client capabilities and structured activity selection contracts."""

from typing import Literal

from pydantic import Field, model_validator

from ._schema import Contract, NonBlankString

ContentFormat = Literal['text', 'diagram', 'animation', 'simulation']


class ClientCapabilities(Contract):
    formats: list[ContentFormat] = Field(default_factory=lambda: ['text'], max_length=4)

    @model_validator(mode='after')
    def unique_formats(self):
        if len(set(self.formats)) != len(self.formats):
            raise ValueError('Client formats must be unique.')
        return self


class ActivitySelection(Contract):
    concept_id: NonBlankString
    format: ContentFormat
    rationale: NonBlankString
