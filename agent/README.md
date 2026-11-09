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
