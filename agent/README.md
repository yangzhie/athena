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

Step 01.2 adds transport-independent Pydantic v2 envelopes. Learning-specific schemas, LLM integration, and service APIs follow in later steps. Keep agent dependencies and configuration separate from other application components.

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
