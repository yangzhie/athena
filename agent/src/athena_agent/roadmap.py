"""Planning data contracts, independent of session storage and providers."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ._schema import Contract, NonBlankString


class TopicScope(Contract):
    scope: Literal['narrow', 'broad']
    rationale: NonBlankString


class Concept(Contract):
    concept_id: NonBlankString
    title: NonBlankString
    description: NonBlankString
    prerequisite_ids: list[NonBlankString] = Field(default_factory=list)


class ConceptGraph(Contract):
    concepts: Annotated[list[Concept], Field(min_length=1)]
    partial_coverage: bool

    @model_validator(mode='after')
    def valid_references(self) -> Self:
        ids = [concept.concept_id for concept in self.concepts]
        if len(set(ids)) != len(ids):
            raise ValueError('Concept IDs must be unique.')
        known = set(ids)
        for concept in self.concepts:
            if len(set(concept.prerequisite_ids)) != len(concept.prerequisite_ids):
                raise ValueError('Prerequisite IDs must be unique per concept.')
            if not set(concept.prerequisite_ids) <= known:
                raise ValueError('Prerequisites must reference concepts in the graph.')
        return self
