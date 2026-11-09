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


from typing import Annotated


class DiagramNode(Contract):
    node_id: NonBlankString
    label: Annotated[NonBlankString, Field(max_length=120)]


class DiagramEdge(Contract):
    from_id: NonBlankString
    to_id: NonBlankString
    label: Annotated[NonBlankString, Field(max_length=120)] | None = None


class DiagramParameters(Contract):
    kind: Literal['diagram'] = 'diagram'
    nodes: Annotated[list[DiagramNode], Field(min_length=1, max_length=12)]
    edges: Annotated[list[DiagramEdge], Field(max_length=24)] = Field(default_factory=list)

    @model_validator(mode='after')
    def valid_edges(self):
        ids = [node.node_id for node in self.nodes]
        if len(set(ids)) != len(ids) or any(edge.from_id not in ids or edge.to_id not in ids for edge in self.edges):
            raise ValueError('Diagram edges must reference unique declared nodes.')
        return self


class AnimationFrame(Contract):
    label: Annotated[NonBlankString, Field(max_length=160)]
    values: Annotated[list[Annotated[float, Field(allow_inf_nan=False)]], Field(min_length=1, max_length=12)]
    highlight_indices: list[Annotated[int, Field(ge=0)]] = Field(default_factory=list, max_length=12)

    @model_validator(mode='after')
    def valid_highlights(self):
        if len(set(self.highlight_indices)) != len(self.highlight_indices) or any(index >= len(self.values) for index in self.highlight_indices):
            raise ValueError('Animation highlights must reference existing values.')
        return self


class AnimationParameters(Contract):
    kind: Literal['animation'] = 'animation'
    frames: Annotated[list[AnimationFrame], Field(min_length=1, max_length=8)]

    @model_validator(mode='after')
    def consistent_frames(self):
        if len({len(frame.values) for frame in self.frames}) != 1:
            raise ValueError('Animation frames must preserve the value count.')
        return self


class SimulationVariable(Contract):
    name: Annotated[NonBlankString, Field(max_length=80)]
    minimum: Annotated[float, Field(allow_inf_nan=False)]
    maximum: Annotated[float, Field(allow_inf_nan=False)]
    initial: Annotated[float, Field(allow_inf_nan=False)]
    step: Annotated[float, Field(gt=0, allow_inf_nan=False)]

    @model_validator(mode='after')
    def valid_range(self):
        if not self.minimum < self.maximum or not self.minimum <= self.initial <= self.maximum or self.step > self.maximum - self.minimum:
            raise ValueError('Simulation controls require valid finite ranges.')
        return self


class SimulationParameters(Contract):
    kind: Literal['simulation'] = 'simulation'
    variables: Annotated[list[SimulationVariable], Field(min_length=1, max_length=4)]
    relationship: Annotated[NonBlankString, Field(max_length=500)]
    observation_prompt: Annotated[NonBlankString, Field(max_length=300)]

    @model_validator(mode='after')
    def unique_variables(self):
        names = [variable.name for variable in self.variables]
        if len(set(names)) != len(names):
            raise ValueError('Simulation variable names must be unique.')
        return self


RichParameters = Annotated[DiagramParameters | AnimationParameters | SimulationParameters, Field(discriminator='kind')]


from .retrieval import VideoReference


class VideoAttachment(Contract):
    reference: VideoReference
    text_alternative: NonBlankString
