# Athena Agent

Independent Python backend for Athena's adaptive learning agent. Product requirements are in [AGENTS.md](../AGENTS.md); local incremental tasks are in [MODULES.md](MODULES.md) (ignored by Git).

## Setup

Install Python 3.12 or newer and uv. Run these commands from `agent/`:

```sh
uv sync
```

This creates a local `.venv`, installs the agent package in editable mode, and installs development dependencies from `uv.lock`.

## Test

```sh
uv run pytest
```

Tests verify package imports and shared contract validation and serialization. No frontend, retrieval service, model credentials, or other running services are required. Initial dependency installation requires access to a Python package registry.

## Build

```sh
uv build
```

The source distribution and wheel are written to `dist/`.

## Project layout

- `src/athena_agent/`: agent package.
- `tests/`: automated tests.
- `pyproject.toml`: package, development dependency, and test configuration.
- `uv.lock`: resolved dependencies for reproducible setup.

## Shared contracts

Step 01.2 adds transport-independent Pydantic v2 envelopes; step 01.3 adds learning contracts. LLM integration and service APIs follow in later steps. Keep agent dependencies and configuration separate from other application components.

```python
from athena_agent.contracts import (
    AgentError,
    AgentRequest,
    ErrorCode,
    ErrorResponse,
    RequestContext,
    SuccessResponse,
)

request = AgentRequest[dict[str, str]](
    context=RequestContext(request_id="req-1", learner_id="learner-1"),
    payload={"topic": "Bubble Sort"},
)
request_json = request.model_dump_json()
restored = AgentRequest[dict[str, str]].model_validate_json(request_json)
schema = AgentRequest[dict[str, str]].model_json_schema()
```

Use concrete payload types when constructing or validating generic envelopes. The dictionary payloads below illustrate the envelopes, rather than defining learning operations or API endpoints.

Request:

```json
{
  "context": {"request_id": "req-1", "learner_id": "learner-1", "session_id": null},
  "payload": {"topic": "Bubble Sort"}
}
```

Success response:

```json
{
  "status": "success",
  "request_id": "req-1",
  "session_id": "session-1",
  "data": {"text": "Ready"}
}
```

Error response:

```json
{
  "status": "error",
  "request_id": "req-1",
  "session_id": null,
  "error": {
    "code": "dependency_unavailable",
    "message": "The learning service is temporarily unavailable.",
    "retryable": true
  }
}
```

- Identifiers are caller-supplied, nonblank strings, preserved exactly; no UUID format is required. Learner identity comes from the host application.
- Session IDs may be omitted or null before a session exists. Response status defaults to its corresponding literal value; `retryable` defaults to false.
- Envelopes reject unexpected fields and implicit type coercion. Payload validation follows the supplied concrete type; nested payload models define their own validation rules.
- Success responses contain `data`; error responses contain `error`. Mixed results are rejected.
- `ErrorCode` supports `invalid_request`, `session_not_found`, `dependency_unavailable`, `invalid_model_output`, and `internal_error`.
- Error messages must be nonblank and safe to display. Callers must keep credentials, internal diagnostics, and stack traces out of messages; these contracts do not sanitize them automatically.
- HTTP mappings, request handling, and exception-to-response translation are left to later modules.

## Learning contracts

Import learning models and discriminated unions from `athena_agent.learning`:

| Contract | Purpose |
| --- | --- |
| `Question` | Multiple-choice or open-ended question, including concept, prompt, and difficulty. |
| `QuestionWithCriteria` | Internal question bundle containing its answer key or expected reasoning. |
| `Answer` | Selected choice or written answer associated with a question. |
| `Assessment` | Outcome, feedback, confidence, misconceptions, and prerequisite gap IDs. |
| `ConceptMastery` | Concept status and supporting assessment IDs. |
| `LearningState` | Goal, current phase/concept, and concept mastery records. |
| `LearningActivity` | Question, explanation, hint, feedback, or completion activity. |

```python
from athena_agent.contracts import SuccessResponse
from athena_agent.learning import (
    OpenEndedCriteria,
    OpenEndedQuestion,
    QuestionActivity,
    QuestionWithCriteria,
)

bundle = QuestionWithCriteria(
    question=OpenEndedQuestion(
        question_id="q-1",
        concept_id="bubble-sort",
        prompt="Why compare adjacent items?",
        difficulty="beginner",
    ),
    criteria=OpenEndedCriteria(
        expected_reasoning="Adjacent comparisons move larger items towards the end.",
    ),
)
response = SuccessResponse[QuestionActivity](
    request_id="req-1",
    data=QuestionActivity(activity_id="activity-1", question=bundle.question),
)
```

Keep `QuestionWithCriteria` agent-internal. Send only its `question` through `QuestionActivity`; that learner-facing model rejects criteria fields. This separation does not replace access control in the eventual API.

- Questions require `beginner`, `intermediate`, or `advanced` difficulty. Multiple-choice questions require at least two unique choice IDs, and bundled criteria must reference an existing choice.
- Assessment outcomes are `correct`, `partial`, `incorrect`, or `uncertain`; confidence is a finite value from 0 to 1 describing assessment certainty, not mastery.
- Mastery is `unknown`, `developing`, or `mastered`. Mastered records require assessment IDs; deciding whether evidence is sufficient belongs to later assessment/orchestration modules.
- Learning phases are `diagnose`, `teach`, `reinforce`, `evaluate`, `progress`, and `complete`. Contracts describe state without implementing transitions.
- Union payloads require a `kind` discriminator. Use `AgentRequest[Answer]` and `SuccessResponse[LearningActivity]` for typed envelopes; use Pydantic `TypeAdapter` to validate a standalone union.
- All models reject unknown fields and blank required text. References to questions, concepts, and assessment evidence are opaque IDs; existence and session ownership must be checked by later services. Submitted answers are validated against a particular question by the later assessment module.
- These contracts implement no generation, scoring, persistence, or UI rendering. Rich content and source references are added in later steps.

## Structured model interface (01.4)

`athena_agent.llm.LLM` defines asynchronous `generate(messages, response_model)`. Messages have an explicit role and nonblank content; the response model is a concrete Pydantic model class. Providers return validated model instances rather than plain chatbot text.

```python
import asyncio
from athena_agent.learning import CompletionActivity
from athena_agent.llm import Message, MockLLM

mock = MockLLM([{"activity_id": "a1", "text": "A focused learning step."}])
activity = asyncio.run(mock.generate(
    [Message(role="user", content="Teach me Bubble Sort")], CompletionActivity,
))
```

The mock accepts model instances, dictionaries, JSON strings, or `LLMError` failures. It consumes them in order, records independent message snapshots in `calls`, and fails explicitly when exhausted. Invalid scripted outputs raise `InvalidOutputError`. Provider-independent failures expose safe messages, a shared error `code`, and `retryable`; `ModelRefusalError` is terminal and uses the `invalid_model_output` code. There are no automatic retries yet.

## Live OpenAI adapter (01.5)

`athena_agent.openai_llm.OpenAILLM` implements the same interface using the official OpenAI Python SDK and Responses structured-output parser. Choose an account-accessible model that supports structured outputs. Set `OPENAI_MODEL` and `OPENAI_API_KEY` in the process environment; no model is chosen automatically and `.env` files are not loaded. Never commit credentials.

```python
from athena_agent.openai_llm import OpenAILLM, OpenAISettings

async def generate_live(messages, response_model):
    async with OpenAILLM(OpenAISettings.from_env()) as llm:
        return await llm.generate(messages, response_model)
```

Configure `timeout` (default 30 seconds) and `max_output_tokens` (default 2,048) through `OpenAISettings`. API keys are excluded from configuration serialization and representation. The adapter requests `store=False`, disables SDK retries, and closes its owned client on exit. An injected SDK client is left open; its request options also disable retries.

Refusals and incomplete responses are terminal failures. Connection/timeouts, HTTP 408/409/429, and server errors are marked retryable; authentication, permissions, and other request errors are terminal. Invalid parsed output raises `InvalidOutputError`. Messages exposed by the adapter contain no raw provider diagnostics. Tests inject a client and make no live API calls.

Reference: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

## Validation and retry policy (01.6)

Wrap any `LLM` in `athena_agent.reliable_llm.ReliableLLM`. Each result must be an instance of the requested response model and is dumped/revalidated to check field and cross-field rules, even if a provider bypassed model construction validation.

```python
from athena_agent.reliable_llm import ReliableLLM, RetryPolicy

async def generate_reliably(provider, messages, response_model):
    llm = ReliableLLM(provider, policy=RetryPolicy(max_attempts=3))
    return await llm.generate(messages, response_model)
```

The default is three total attempts with 0.5- and 1-second delays. `initial_delay`, `max_delay` (default 30 seconds), and `max_attempts` are configurable. Retries cover classified transient dependencies and invalid model outputs. Refusals, authentication, permission, invalid-request, and unexpected failures are terminal. Terminal exception messages are sanitized; cancellation propagates unchanged. The wrapper leaves provider ownership/closing to its caller and changes no learning state. Tests inject a sleeper to verify attempts and delays without waiting.

## Retrieval contracts and mock (01.7)

`athena_agent.retrieval.Retriever` defines asynchronous `retrieve(RetrievalRequest) -> RetrievalResult`. Requests carry a nonblank query, optional nonempty `source_ids` scope, and `max_results` (default 5). An omitted scope means all sources accessible to the host's retrieval service; it does not grant access to other learners' materials.

Results contain discriminated `DocumentPassage` and `VideoSegment` items. Documents preserve source/passage IDs, title, text, and optional page (1-based), section, and source URI. Videos preserve source/segment IDs, title, transcript excerpt, optional URI, and finite timestamps in seconds with end strictly after start. URIs may be host-specific references, not just public URLs. Stable IDs resolve through the external service; the agent neither verifies that a source exists nor invents references.

```python
import asyncio
from athena_agent.retrieval import MockRetriever, RetrievalRequest, RetrievalResult

mock = MockRetriever([RetrievalResult()])
result = asyncio.run(mock.retrieve(RetrievalRequest(query="Bubble Sort")))
assert result.items == []  # Successful retrieval with no matches.
```

Supply model instances or dictionaries to script document/video results, or `RetrievalError` instances to script failures. `MockRetriever` records independent request snapshots, preserves supplied source metadata, applies source filtering and result limits, and fails explicitly when exhausted. It does not perform semantic search. Example document/video data in `tests/fixtures/retrieval.json` is fictional test content.

`RetrievalResult` also provides the contract for externally supplied results. Keep retrieved text as untrusted source data; grounding and protection against instructions inside sources arrive in module 08. Authentication, source authorization, uploads, ingestion, indexing, transcription, clipping, and playback remain the host/external services' responsibility.

## In-memory conversations (02.1)

`athena_agent.conversation.InMemoryConversationStore` provides synchronous `create(context)`, `read(context)`, and `append_turn(context, turn)`. Use a `RequestContext` containing caller-supplied learner/session IDs. A `ConversationTurn` contains nonblank `user_text` and `assistant_text` and converts to ordered LLM messages with `messages()`.

Sessions are keyed by learner and session, duplicate creation fails without replacing history, and missing/cross-learner sessions produce the same `SessionNotFoundError`. Reads and writes return independent snapshots. This is process-local memory, not durable storage or authentication; the host must supply a trusted learner identity. Completed turn pairs are stored together so partial exchanges cannot enter history.

## Goals and discussion context (02.2)

Use `store.initialize_goal(context, goal)` once to start a `TopicContext` with a generated topic ID and fresh `LearningState`. The goal is stored only in `learning_state.goal`. `store.update_focus(context, focus)` updates or clears the discussion focus without changing mastery or phase. Invalid changes leave stored state untouched.

An active topic tracks its own turn history; `session.history` retains the full chronological conversation, including turns before goal initialisation. `append_turn` updates both histories when a topic is active. Returned topic state is independently copied. Goal changes are handled by the later topic-switch operation, not by repeated initialisation.

## Contextual conversations (02.3)

Construct `ConversationManager(store, llm)` from `athena_agent.conversation_manager` and call `await manager.send(context, text)` after creating a session and initialising its goal. It returns `ConversationReply(text, discussion_focus)`. Inject `MockLLM` for deterministic conversations; providers are wrapped in `ReliableLLM` unless already wrapped.

A structured intent call distinguishes continuations, requests for clarification, explicit topic changes, and ambiguous intent. Continuations/clarifications get a second call for a contextual reply. Ambiguous requests return a clarifying question without changing the goal or focus. Topic switching is connected in 02.4. Replies do not assess mastery or advance learning phases.

Each successful interaction atomically appends its user/assistant pair and updates focus. Failures and cancellation do not append partial turns. A store-owned per-session async lock serialises managers sharing that store; revision checks reject stale writes caused by synchronous out-of-band changes. This is a single-process, single-event-loop service boundary; it is not distributed locking or durable persistence.

## Topic changes (02.4)

An explicit, unambiguous topic-change decision archives the active `TopicContext` in `session.archived_topics` and creates a new topic ID and fresh `LearningState`. Classification may consult the current topic to understand the request, but the new topic's reply receives only fresh state and the current message. Old mastery, focus, and turns are not included.

The switch and its reply commit together. Failed or cancelled generation preserves the previous active topic without creating an archive. Ambiguous changes trigger clarification, and comparisons/examples stay in the existing topic. All turns remain in chronological `session.history`; archived topic snapshots can be inspected via `store.read`. Automatic topic restoration is not implemented. Intent interpretation is model-based and should receive live quality evaluation before production use.

## Context budgets (02.5)

`athena_agent.context.ContextBuilder` is used for both intent classification and reply generation. It always retains application instructions, the active goal and structured learning state, discussion focus, and the full current user message. It then selects the newest contiguous suffix of complete user/assistant turns that fits. Archived topics are excluded; no stored history is deleted or summarised.

```python
from athena_agent.context import ContextBudget, ContextBuilder
from athena_agent.conversation_manager import ConversationManager

builder = ContextBuilder(ContextBudget(context_window=16384, output_reserve=2048))
# manager = ConversationManager(store, llm, context_builder=builder)
```

The total estimate includes serialized messages, the requested response model's JSON Schema, output reserve, a framing allowance (default 512), and a per-message allowance (default 32). The default counter uses UTF-8 byte length as a conservative estimate, not an exact provider tokenizer. Supply a `TokenCounter` with `count(text) -> int` for a model-specific estimator; configure the context window for your selected model and keep the output reserve at least as large as the adapter's output-token limit. Provider-specific schema/framing overhead can vary, so retain headroom.

When mandatory context exceeds the budget, `ContextBudgetError` reports `invalid_request` without a model call or silent truncation. If a later reply cannot fit after routing, the entire pending interaction still rolls back. Selection never skips a newer oversized turn to insert older discussion, which would distort conversational continuity.

## Goal interpretation (03.1)

`athena_agent.planning.PlanningService(llm, context_builder=...)` exposes explicit planning calls without changing `ConversationManager.send`. `await planner.interpret_goal(text, clarification_turns=())` returns a `GoalInterpretation`: either `status="resolved"` with a goal, or `status="clarification"` with one focused question. Supply prior `ConversationTurn` pairs and the latest learner message to resolve clarification across calls.

Interpretation uses the existing bounded context builder and reliable LLM interface. It creates no session and changes no stored goal. The caller may initialise a session only after resolution. No proficiency, assessment, or mastery is inferred from interpreting a goal.

## Topic scope (03.2)

`await planner.classify_scope(goal)` returns `athena_agent.roadmap.TopicScope(scope, rationale)`, classifying the resolved goal as `narrow` or `broad`. Scope describes the requested conceptual coverage, not learner proficiency. A focused outcome within a broad field can still be narrow. This is a standalone call with no session mutations or automatic conversation integration; scope quality requires live-model evaluation beyond deterministic fixtures.

## Concepts and prerequisites (03.3)

`await planner.identify_graph(goal, scope)` returns `ConceptGraph(concepts, partial_coverage)`. Concepts have stable IDs, titles, descriptions, and prerequisite IDs referring to concepts in the same graph. Empty graphs, duplicate IDs, duplicate prerequisites, and missing references are rejected. Stable IDs are model-proposed identifiers, not display titles; later revisions must preserve retained identities.

`PlanningPolicy(initial_concept_limit=12)` bounds initial generation in both the response schema and validation. Broad subjects must return an initial foundation marked `partial_coverage=true`; full coverage is not claimed. Additional planning inputs are included in the context budget through `ContextBuilder.build(..., additional_context=...)`. Graph generation remains independent of sessions; cycle validation is added with complete roadmaps in 03.5.

## Objectives and difficulty (03.4)

`await planner.enrich_graph(graph, goal=goal, learner_state=None)` returns an `EnrichedGraph` with one or more learning objectives and an existing difficulty level per concept. Optional learner state must match the goal. Supplied mastery/evidence is context only and is never changed.

The model returns an `ObjectiveBatch` containing IDs, objectives, and difficulty only. The service requires exactly the original ID set and merges results into the unchanged graph, preserving titles, descriptions, ordering, and prerequisites. Unexpected IDs or attempts to return changed edges are rejected; empty/blank objectives and unknown difficulty levels are invalid.

## Session roadmaps (03.5)

Pass `store=store` to `PlanningService`, then call `await planner.plan(context)` after goal resolution and session initialisation. The service classifies scope, generates the bounded graph, enriches objectives, and saves a `Roadmap` on `session.active_topic.roadmap` in one transaction. Failed, cancelled, oversized, or stale planning leaves the topic unchanged. A second `plan` call rejects an existing roadmap; use revision rather than replacing it blindly.

`Roadmap` holds the goal, `TopicScope`, and `EnrichedGraph`; graph validation now rejects self-dependencies and cycles as well as broken references. `roadmap.eligible_concept_ids(learning_state)` returns unmastered concepts whose prerequisites are demonstrated as mastered. The returned options are not a mandatory sequence and do not advance phase or alter mastery. Topic validation keeps roadmap and learning-state goals consistent. Archived topics retain their own roadmap; new conversation topics start without one. Ordinary conversation sends still make no automatic planning calls.

## Roadmap revision (03.6)

`await planner.revise(context, requested_change=None)` revises an existing active roadmap using current learner evidence. Supply a request to refine depth/outcome within the same subject; omit it for evidence-driven revision without changing the goal. Unrelated subjects return a `ConversationError` directing the caller to the existing conversation topic-switch flow.

Each revision can add at most `PlanningPolicy.initial_concept_limit` new concept IDs (default 12), independently of how many old nodes are removed. Retained concept IDs, titles, and descriptions cannot be repurposed; objectives, difficulty, and valid prerequisite relationships may change. Renaming an existing title to a fresh ID and reusing an absent historical mastery ID are rejected rather than guessing identity. Restoring removed historical concepts is not implemented. Referenced prerequisites must remain in the graph, and broad roadmaps continue to mark coverage as partial.

Goal refinements update the learning-state and roadmap goals together. All mastery/evidence records, conversation history, and topic identity are preserved, including mastery for concepts removed from the current graph. Removing the current concept clears its pointer; phase/progression decisions remain the future orchestrator's responsibility. Proposal generation, enrichment, and save are atomic under the same session lock and revision checks as conversations. Errors, cancellation, stale state, or context overflow never replace the old roadmap.

Example integration sequence (all methods are backend calls): interpret/clarify the goal, create a session and initialise its resolved goal, call `plan(context)`, then call `revise(context)` when new evidence is available. Planning is explicit throughout; no frontend, retrieval service, or automatic conversation hooks are required. Mock fixtures cover Bubble Sort and an initial Machine Learning foundation with prerequisite gaps. Model judgement about scope, relatedness, and pedagogical quality still needs optional live evaluation.

## Multiple-choice assessment generation (04.1)

`AssessmentService(store, llm, context_builder=...)` in `athena_agent.assessment` exposes `await service.generate_multiple_choice(context, concept_id)`. It requires a concept in the active topic's roadmap, targets its objectives and difficulty, assigns application-generated question/activity IDs, and saves atomically under the existing session lock/revision checks.

Only a `QuestionActivity` is returned. Its private `QuestionRecord` retains `QuestionWithCriteria` in `topic.question_records`; store snapshots are internal backend data and must never be returned wholesale to learners. Invalid generation, cancellation, context overflow, or stale writes do not append a question. Generating questions does not change mastery, phase, or conversation history.

## Open-ended assessment generation (04.2)

`await service.generate_open_ended(context, concept_id)` generates reasoning/application questions with private expected reasoning. Both question-generation methods accept an optional `difficulty="beginner" | "intermediate" | "advanced"` override; it changes the generated question, not the roadmap. Invalid overrides fail before any model call. All generation shares topic ownership, bounded context, atomic storage, and learner-facing question serialization. It does not evaluate an answer or update mastery.

## Answer evaluation (04.3)

`await service.evaluate(context, answer, hint_used=False)` accepts the existing `MultipleChoiceAnswer` or `TextAnswer` contracts. It validates active-topic question ownership and answer format; removed concepts cannot receive new assessments. Multiple-choice grading uses the stored key without an LLM call. Its confidence of 1 describes grading certainty, not demonstrated mastery.

Open-ended reasoning is evaluated against private criteria, with exact answer quotes supporting decisive feedback. Unsupported quotes are rejected. `AssessmentPolicy(evaluation_confidence_threshold=0.8)` converts lower-confidence judgements to `uncertain`. A successful evaluation records the answer, assessment, evidence quotes, and trusted host-supplied hint-use metadata atomically. It does not yet change mastery.

Only one answer is recorded per question. An identical answer and hint status returns the saved assessment without another model call or write; changed answers/status require a fresh question. Failures and cancellation do not save partial evidence. Topic records enforce unique question/assessment IDs and matching references. Full store snapshots contain private criteria and remain backend-only.

## Misconceptions and prerequisite gaps (04.4)

`await service.diagnose(context, assessment_id)` records a structured `Diagnosis` for an existing assessment. Findings carry a `suspected`/`supported` status, exact answer-evidence quote, and confidence. Prerequisite findings may only reference ancestors of the assessed concept in the active roadmap. A selected option alone never proves a misconception; supported findings require decisive partial/incorrect written reasoning and sufficient confidence.

An empty diagnosis is a successful result, distinct from a dependency failure. Repeated diagnosis returns its saved result without another call. Assessment grades, feedback, confidence, and learning state remain unchanged; misconception summaries preserve their status prefix, while prerequisite summaries contain concept IDs (consult the diagnosis for certainty). Diagnosis does not mark prerequisites mastered or change progression. All updates share atomic session writes and safe model failure handling.

## Evidence-based mastery (04.5)

Every new evaluation now updates concept mastery in the same atomic write. `MasteryPolicy` defaults to two latest decisive, high-confidence (`>=0.8`), unhinted correct assessments, with at least one open-ended reasoning/application response. Distinct question IDs and distinct normalized prompts are required. Multiple-choice successes alone cannot establish mastery; a later decisive partial/incorrect response returns the concept to `developing`. Hint-assisted successes cannot satisfy the mastery window.

Uncertain or low-confidence records neither promote nor demote existing mastery; without prior decisive evidence the status is `unknown`. Every assessment ID is retained, including uncertain and historical references, but historical IDs without full local records do not count as new proof. These are configurable starting rules, not validated pedagogical constants.

Pass `mastery_policy=MasteryPolicy(...)` to `AssessmentService`, or call `await service.recompute_mastery(context, concept_id=None)` to recompute explicitly from recorded evidence. Unchanged recomputations and identical answer retries do not write again. Recomputing includes removed concepts with historical evidence and preserves unrelated mastery records. Neither assessment nor diagnosis automatically advances phase, marks prerequisites mastered, or progresses lessons.

## Follow-up verification (04.6)

`await service.generate_followup(context, assessment_id)` returns a fresh open-ended question for the parent's concept and difficulty. It uses the previous question, answer, and assessment to request a new reasoning/application example, and rejects normalized prompts already used for that concept. The private record links to its parent assessment. Identical generation requests return the same activity without another model call, including concurrent requests.

Assess follow-ups through `evaluate` as usual. A correct selection followed by successful independent reasoning can satisfy the mastery policy; contradictory follow-up evidence leaves or returns the concept to developing without proving that the earlier answer was guessed. The model is explicitly instructed not to make that claim. Topic validation checks parent existence, concept consistency, and one follow-up per parent; archives retain old records while new topics start empty. Teaching, automatic question initiation, progression, and retrieval grounding remain later modules.

## Targeted microlearning

`TeachingService(store, llm).explain(context, assessment_id)` returns an
`ExplanationActivity` for one gap from an incorrect, partial, or uncertain assessment
in the active roadmap. Correct answers alone do not identify a gap. Explanations
are limited to 120 words and 1000 characters and use the concept objectives,
question, answer, and feedback without sending private criteria to the teaching
model. Generation changes no history, evidence, mastery, or phase. Cancellation,
context overflow, dependency failures, and stale snapshots return no activity.
Pedagogical relevance is model judgement; deterministic checks verify contracts
and targeting inputs rather than asserting live teaching quality.

Run the repeatable offline behavioral evaluation from `agent/`:

```sh
uv run python -m athena_agent.evaluation tests/fixtures/teaching.json
```

It emits a JSON result and exits nonzero on a failed check. Fixtures and scripted
models make no network calls. Source archives explicitly include only application
source, application tests, README, pyproject, and lockfile; local workflow tooling
is excluded.

`await teaching.example(context, assessment_id)` returns a concise worked practical
example for the same gap. `await teaching.hint(context, question_id)` returns a
`HintActivity` offering one reasoning step for an unanswered active-topic question;
its model input omits the private key and rubric. Answered, removed, and foreign
questions are rejected. These explicit calls change no evidence or state. The host
must pass `hint_used=True` when submitting a hint-assisted answer to assessment;
requesting a hint does not itself submit or grade an answer. Whether a model hint
reveals too much remains a pedagogical evaluation concern.

Follow-up generation also accepts `purpose="application"` or `purpose="retention"`.
Application requests transfer to a new concrete situation; retention requests
unaided recall and explanation. The default remains `verification`. Each parent
assessment has one cached follow-up per purpose, and all purposes reject reused
concept prompts. Assess these questions through the existing evaluation service;
generation alone never proves retention or changes mastery. Delayed delivery and
scheduling belong to the host, so an immediate recall check makes no claim about
long-term retention.

Teaching changes approach from recorded concept evidence: two consecutive decisive
partial/incorrect assessments request smaller worked steps, and four request an
analogy mapped back to the concept. A decisive correct answer resets this count;
uncertain, low-confidence (`<0.8`), and other-concept records do not contribute.
Repeated explanation requests alone never count as struggles. These conservative
starting thresholds affect teaching style only, never assessment grades or mastery.

`await teaching.recommend_format(context, concept_id)` returns a typed
`FormatRecommendation` with `text`, `diagram`, `animation`, or `simulation` and a
short rationale tied to concept objectives. Instructions prefer text unless a
richer format has a specific benefit. Recommendations contain no executable UI;
client capability selection and structured activity parameters are separate
integration concerns. This read-only operation uses the same bounded context,
validation, retry, ownership, and stale-result checks as explanations.

## Proactive session start

`LearningOrchestrator(store, llm).start(context, goal, difficulty="beginner")`
plans a resolved goal and returns the first diagnostic question for an eligible
prerequisite concept. Use `PlanningService.interpret_goal` to clarify ambiguous
goals before starting. The optional beginner/intermediate/advanced difficulty is
a diagnostic starting level supplied by the host, never evidence of mastery.
Narrow and broad goals use the existing planner; broad roadmaps remain partial.
The current question is saved on the active topic. Preparation uses existing
services on an isolated snapshot; only a complete roadmap and diagnostic become
visible. Failure/cancellation leaves no partial session, and concurrent starts
for one learner/session serialize. Duplicate existing sessions are rejected.

The offline runner also accepts `tests/fixtures/session_start.json`, covering
narrow/broad goals at beginner/advanced diagnostic levels with independent mock
scripts. These scenarios check scope contracts and proactive behavior without
assuming that declared proficiency proves understanding.

`await orchestrator.answer(context, answer, hint_used=False)` evaluates the current
question, teaches an assessed gap, requests independent reasoning after a correct
selection, or diagnoses the next eligible concept after demonstrated mastery.
`await orchestrator.continue_learning(context, explanation.activity_id)` follows a
teaching unit with an application question. Each turn stages all downstream calls
before committing evidence, mastery, current activity, and the conversation pair
together. Failures and cancellation roll back the turn. Identical answer retries
return the original resulting activity; changed answers are rejected. A fully
mastered current roadmap enters `progress`; broader completion policy is separate.

Run `uv run python -m athena_agent.evaluation tests/fixtures/learning_loop.json`
for bundled offline scenarios checking partial/incorrect reasoning after a correct
selection, misconception evidence, conversation continuity, topic isolation, and
budgeted history selection. Mock grades exercise evidence-handling behavior;
they do not measure real-model grading accuracy.

`orchestrator.next_action(context, assessment_id)` exposes a read-only
`LearningDecision` (`teach`, `verify`, `diagnose`, or `progress`) with a concept and
reason. Answer submission uses the same deterministic selector. Missing
prerequisites take priority over dependent-concept verification; new concepts
must be eligible under the roadmap's evidence-based prerequisite checks.

The shared `adjust_learning(topic, concept_id)` policy lowers question difficulty
one level after two decisive failures and raises it one level after two successive
unhinted successes, within beginner–advanced bounds. Uncertain evidence is ignored.
It requests scaffolded explanations and one-unit pacing during struggles; successes
favor application checks. Orchestrated follow-ups and next diagnostics use these
adjustments, and mastered strengths remain excluded from candidate selection.
The original roadmap difficulty and mastery evidence are preserved. Explicit
follow-up difficulty overrides cannot replace an already cached question.

Supported high-confidence prerequisite findings trigger a fresh diagnostic for
that prerequisite, including a recheck of previously mastered evidence. Diagnosis
alone never demotes prerequisite mastery. Four decisive unsuccessful concept
attempts select `recover`: a smaller worked example followed by a single-step
application task, with existing difficulty/depth adaptation. Suspected findings
remain hypotheses and do not alone trigger prerequisite rechecks.

A narrow roadmap with full coverage finishes only after all concepts have mastery
evidence, sets phase `complete`, and clears the current concept. Broad subjects
and partial roadmaps instead revise their roadmap from accumulated evidence and
proactively diagnose a new eligible concept. Broad coverage remains explicitly
partial. An expansion that produces no eligible learning target is invalid;
dependency failures or invalid revisions roll back the pending answer, allowing
retry without false completion or lost evidence.

Automatic expansion preserves the existing topic scope; a model cannot silently
narrow a broad subject into a fully covered topic. Scope changes require an
explicit planning operation rather than implicit progression.

## Local text learning journey

```sh
uv run python -m athena_agent.runner tests/fixtures/text_journey.json
```

The runner composes the real orchestrator, planning, teaching, and assessment
services with a scripted mock model and in-memory storage. A wrong diagnostic
answer receives a concise targeted unit, followed by application and independent
reasoning before mastery and narrow-topic completion. The JSON transcript exposes
learner-facing text, phases, and mastery counts. Behavioral expectations fail the
process exit code. The same fixture works through `athena_agent.evaluation` and
checks targeted teaching, conciseness, adaptive phases, and mastery decisions.
No credentials, network, frontend, or paid model calls are used.

## Learning-memory interface

`athena_agent.memory.LearningMemoryStore` defines identity-scoped session snapshots,
atomic compare-and-save, and per-session interaction/creation contexts. Existing
conversation, planning, teaching, assessment, and orchestration services depend on
this protocol. `InMemoryLearningMemory` names the established
`InMemoryConversationStore` implementation; it is an alias, preserving existing
integrations and avoiding duplicate memory services. Returned snapshots are copies;
private assessment criteria make whole-session snapshots backend-only.

`store.load_conversation(context)` exports a validated `ConversationMemory` with
session history and active/archived topic goals, focus, and topic history.
`store.save_conversation(context, memory, expected_revision=revision)` restores it
atomically to an existing session with the same host identity. Existing learning
topics and evidence are preserved; replacing topics or goals through conversation
restore is rejected. Restoring into an empty session creates conversation context
without inventing learning evidence. Exported snapshots contain no private criteria.
Use the revision from `store.read` for compare-and-save; stale imports fail.

`load_learning(context)` and `save_learning(context, memory, expected_revision=...)`
handle a separate private `LearningMemory` snapshot: roadmaps, mastery, assessment
evidence/diagnosis, question records, and current activity, including archived
topics. It contains no conversation history or focus. Save validates evidence
references and topic/goal/identity/revision compatibility atomically, while
preserving existing conversation data. To restore both projections into an empty
session, save conversation then learning using the updated revision. Learning
snapshots include private keys and criteria and must remain backend-only.

## Durable SQLite memory and resume

Use `SQLiteLearningMemory("/path/to/agent-memory.sqlite")` as the injected store.
It implements the same interface and reuses existing validated domain operations.
Conversation and private learning projections occupy separate JSON columns and
update together in one SQLite statement with a revision comparison. A composite
learner/session primary key isolates records; independent adapter instances reject
stale writes. No database transaction stays open during model calls. Use a context
manager or `close()` to release the connection. Database files are host-managed
private backend data and must not be exposed as client artifacts.

`orchestrator.resume(context)` returns a copied current activity with no model
call after reopening the database. Failed/incomplete model operations never publish
partial evidence. Storage failures use a safe `dependency_unavailable` error.
The schema stores version 1 records and fails closed on unsupported versions;
a migration system is not implemented.

Answer idempotency survives database reopen and races between independent SQLite
adapters. If a revision conflict reveals that the identical question answer and
hint metadata already committed, the orchestrator returns that accepted activity,
never its losing generated draft. Evidence, mastery, history, and revision advance
once. Changed answers or hint metadata remain conflicts; unrelated stale writes
still fail rather than overwriting newer context. Concurrent callers may each
perform model generation, but only one learning-state transaction is accepted.

Hosts may inject `LearnerScopedMemory(store, trusted_learner_id)` to bind all memory
operations to the learner resolved by their authentication layer. It rejects
contexts naming any other learner, including existing sessions, with the same
unavailable-session error. It delegates storage, preserves session-level keys,
and implements no accounts or authentication itself. Never derive the binding
from untrusted client JSON.

The offline fixture `tests/fixtures/memory_journey.json` verifies SQLite reopen,
current-activity resumption, duplicate replay, and learner isolation with colliding
session IDs through `athena_agent.evaluation`.

## Selected learning materials

`KnowledgeService(store, retriever).retrieve(context, query, source_ids=None,
max_results=5)` requests relevant document passages and video references through
the established retrieval interface and saves a copied selection on the active
topic. The host supplies an authorized retriever; source IDs do not grant access.
Returned scope/limit violations fail, and stale writes, cancellation, or dependency
failures preserve the prior selection. `None` means no selected materials; an
empty result records a successful search without matches. Selection is durable
learning memory and follows topic/learner isolation. No search infrastructure,
ingestion, transcription, or video processing is implemented here.

`await KnowledgeService(store).supply(context, retrieval_result, source_ids=None,
max_results=5)` accepts host-authorized external results through the same typed
selection contract, scope validation, topic storage, and snapshot copying.
It requires no retriever. Malformed or out-of-scope supplied data is an invalid
request; unavailable retrieval is a dependency failure. An empty external result
remains an explicit empty selection rather than silently enabling general knowledge.

Selected materials now enter the bounded planning, teaching, and assessment
context. Source-based generation requests only supported domain content and runs
a second structured support check requiring exact quotes resolving to selected
passages/transcripts. Unsupported content or fabricated evidence fails before
state publication; empty selections cannot silently produce general-knowledge
content. Semantic support still depends on model judgement, while quote/reference
integrity is deterministic. General-knowledge calls keep their original call path.
`orchestrator.start(..., materials=retrieval_result)` can select materials before
planning a new session. Selection and private criteria remain backend data.

Grounded activities, assessments, and roadmaps return typed `sources`. Each
citation copies identifiers, title, URI, page/section or exact supplied video
start/end times from verified evidence, plus its exact quote. Models select
source indices and quotes; they cannot generate citation metadata. Question
citations are retained with private records for replay and deterministic grading.
Internal generation provenance is excluded from schemas and serialization.

Source-based generation reports `insufficient_evidence` when selected materials
cannot support the requested content and `conflicting_sources` when the support
check identifies conflicting supplied evidence. Conflict reports must resolve exact
quotes in at least two selected items. These safe, nonretryable errors preserve
learning state and ask for more relevant materials or source clarification; the
agent never silently picks a source winner. Retrieval unavailability remains a
separate `dependency_unavailable` failure and preserves the previous selection.

Activities, assessments, and roadmaps label `knowledge_origin` as `general`,
`materials`, or `supplement`. Verified citations imply `materials`; supplements
cannot claim material citations. With no selection, learning uses general knowledge.
`await teaching.supplement(context, assessment_id)` explicitly requests a bounded
general-knowledge supplement to selected materials, keeps the selection intact,
and labels its result without citations. It is never an automatic response to
insufficient evidence. `await knowledge.use_general_knowledge(context)` explicitly
clears selection when the host chooses to leave source-only learning.

Source commands, role markers, grading requests, and instructions to reveal
criteria have no authority. Intent routing excludes retrieved text entirely;
source-based conversation replies also pass the support check. Verification
rejects detected source-instruction following, and schemas cannot accept generated
mastery or state updates. Source text stays in data messages, never system prompts.
Run `tests/fixtures/source_safety.json` through the offline evaluator for grounded
content/citation checks, unsupported claims, forged evidence, malicious source
commands, and generated state-mutation attempts. Model-based detection is a
layer of defense; deterministic state transitions and strict contracts remain
the state-integrity boundary.

## Structured teaching and feedback

`ExplanationActivity.content` optionally describes one `TeachingContent` unit with
a summary, up to four steps, and a worked example. Generated explanations always
populate it, deriving a summary from text-only model responses. Structured content
is bounded to 120 words/1000 characters and retains the existing complete `text`
alternative. `AssessmentService.feedback_activity(context, assessment_id)` returns
structured outcome/message feedback from saved evidence without exposing criteria,
generating another grade, or changing state. Existing text-only activity payloads
remain valid; clients own presentation and rendering.

`orchestrator.progress(context)` derives a learner-facing `ProgressSummary` with
concept titles/status/evidence counts, mastered/total counts, prerequisite-eligible
concept IDs, phase, coverage, and `next_step` (`answer`, `continue`, `plan`, `expand`,
or `complete`). Completion requires the actual narrow full-coverage mastery rule;
broad partial coverage is never reported complete. The projection makes no model
calls or state changes and excludes private question/assessment records.
