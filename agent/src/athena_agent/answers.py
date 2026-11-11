"""Concise answers with server-owned source attribution and bounded repair."""
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field

from ._schema import Contract, NonBlankString
from .grounding import EvidenceError, verify_grounding
from .context import ContextBuilder
from .conversation import TopicContext
from .llm import LLM
from .retrieval import SourceReference


class ReplyDraft(Contract):
    text: NonBlankString
    discussion_focus: NonBlankString | None = None


class AnswerPart(Contract):
    text: Annotated[NonBlankString, Field(max_length=2000)]
    origin: Literal['materials', 'general']


class AnswerDraft(Contract):
    parts: Annotated[list[AnswerPart], Field(min_length=1, max_length=4)]
    discussion_focus: NonBlankString | None = None


@dataclass
class AnswerResult:
    text: str
    discussion_focus: str | None
    sources: list[SourceReference]
    origin: Literal['materials', 'supplement', 'general']


async def answer_question(llm: LLM, builder: ContextBuilder, topic: TopicContext, text: str, instructions: str) -> AnswerResult:
    instructions += (
        '\nAnswer the current question directly and concisely before adding examples. '
        'Use retrieved material whenever it supports the requested distinction, including information '
        'spread over multiple passages. Course directions and learning objectives are legitimate context. '
        'Never claim that an entire Offering lacks a topic based on the passages retrieved. '
        'If coverage is incomplete, still answer with clearly attributed general knowledge. '
        'Do not refuse solely because the material does not cover the question.'
    )
    if topic.knowledge is not None and topic.knowledge.items:
        last = None
        for attempt in range(2):
            repair = ('\nThe previous attempt was not fully supported. Keep the supported core answer; '
                      'remove unnecessary details or move unsupported additions into general parts.' if attempt else '')
            messages = builder.build(topic, text, instructions + repair +
                '\nReturn attributed parts. Use origin=materials for source-supported claims and '
                'origin=general for additions. Do not invent citations or coverage claims.', AnswerDraft, allow_general=True)
            last = await llm.generate(messages, AnswerDraft)
            try:
                sources = await verify_grounding(llm, builder, topic, last, mixed=True)
            except EvidenceError as error:
                if error.code != 'insufficient_evidence':
                    raise
                continue
            # If an entirely "general" draft was verified against sources, it is
            # actually grounded. The model cannot hide supported content behind
            # an unsupported coverage claim merely by choosing the general tag.
            mixed = any(p.origin == 'materials' for p in last.parts) and any(p.origin == 'general' for p in last.parts)
            if mixed:
                rendered = '\n\n'.join(
                    ('**From your material:** ' if p.origin == 'materials' else '**General-knowledge addition:** ') + p.text
                    for p in last.parts)
            else:
                rendered = '\n\n'.join(p.text for p in last.parts)
            return AnswerResult(rendered, last.discussion_focus, sources, 'supplement' if mixed else 'materials')
        # Verification has already checked conflicts and source instructions. An
        # all-general final draft can be returned without another generation.
        if last and all(p.origin == 'general' for p in last.parts):
            return AnswerResult('\n\n'.join(p.text for p in last.parts), last.discussion_focus, [], 'general')
    general_topic = topic.model_copy(update={'knowledge': None})
    messages = builder.build(general_topic, text, instructions +
        '\nGive a general-knowledge answer. Do not claim that it is supported by the uploaded material.', ReplyDraft)
    reply = await llm.generate(messages, ReplyDraft)
    return AnswerResult(reply.text, reply.discussion_focus, [], 'general')
