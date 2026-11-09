"""Planning data contracts, independent of session storage and providers."""

from graphlib import CycleError, TopologicalSorter
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ._schema import Contract, NonBlankString
from .learning import Difficulty, LearningState
from .retrieval import SourceReference


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
        if any(concept.concept_id in concept.prerequisite_ids for concept in self.concepts):
            raise ValueError('Concepts cannot depend on themselves.')
        try:
            tuple(TopologicalSorter({
                concept.concept_id: set(concept.prerequisite_ids) for concept in self.concepts
            }).static_order())
        except CycleError:
            raise ValueError('Concept prerequisites must not contain cycles.') from None
        return self


class ConceptObjectives(Contract):
    concept_id: NonBlankString
    objectives: Annotated[list[NonBlankString], Field(min_length=1)]
    difficulty: Difficulty


class ObjectiveBatch(Contract):
    concepts: Annotated[list[ConceptObjectives], Field(min_length=1)]

    @model_validator(mode='after')
    def unique_concepts(self) -> Self:
        ids = [concept.concept_id for concept in self.concepts]
        if len(set(ids)) != len(ids):
            raise ValueError('Objective concept IDs must be unique.')
        return self


class EnrichedConcept(Concept):
    objectives: Annotated[list[NonBlankString], Field(min_length=1)]
    difficulty: Difficulty


class EnrichedGraph(ConceptGraph):
    concepts: Annotated[list[EnrichedConcept], Field(min_length=1)]


class Roadmap(Contract):
    sources: list[SourceReference] = Field(default_factory=list)
    goal: NonBlankString
    scope: TopicScope
    graph: EnrichedGraph

    @model_validator(mode='after')
    def broad_coverage_is_partial(self) -> Self:
        if self.scope.scope == 'broad' and not self.graph.partial_coverage:
            raise ValueError('Broad subjects require a partial initial roadmap.')
        return self

    def eligible_concept_ids(self, state: LearningState) -> list[str]:
        """Return options, not a mandatory lesson sequence; mutate no state."""
        state = LearningState.model_validate(state.model_dump())
        if state.goal != self.goal:
            raise ValueError('Learning state must match the roadmap goal.')
        mastered = {record.concept_id for record in state.mastery if record.status == 'mastered'}
        return [
            concept.concept_id for concept in self.graph.concepts
            if concept.concept_id not in mastered and set(concept.prerequisite_ids) <= mastered
        ]


class RoadmapRevision(Contract):
    relation: Literal['same_topic', 'unrelated']
    goal: NonBlankString | None = None
    scope: TopicScope | None = None
    graph: ConceptGraph | None = None

    @model_validator(mode='after')
    def complete_proposal(self) -> Self:
        fields = (self.goal, self.scope, self.graph)
        if self.relation == 'same_topic' and any(value is None for value in fields):
            raise ValueError('Same-topic revisions require a goal, scope, and graph.')
        if self.relation == 'same_topic' and self.scope.scope == 'broad' and not self.graph.partial_coverage:
            raise ValueError('Broad revisions must identify partial coverage.')
        if self.relation == 'unrelated' and any(value is not None for value in fields):
            raise ValueError('Unrelated goals must use topic switching instead of a revision graph.')
        return self
