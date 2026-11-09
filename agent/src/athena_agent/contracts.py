"""Transport-independent envelopes for agent requests and responses."""

from typing import Generic, Literal, TypeVar

from ._schema import Contract as _Contract, NonBlankString as _NonBlankString

__all__ = [
    "AgentError",
    "AgentRequest",
    "ErrorCode",
    "ErrorResponse",
    "RequestContext",
    "SuccessResponse",
]

_Payload = TypeVar("_Payload")

ErrorCode = Literal[
    "invalid_request",
    "session_not_found",
    "dependency_unavailable",
    "invalid_model_output",
    "internal_error",
    "insufficient_evidence",
    "conflicting_sources",
]


class RequestContext(_Contract):
    """Caller-provided identifiers; learner identity is supplied by the host."""

    request_id: _NonBlankString
    learner_id: _NonBlankString
    session_id: _NonBlankString | None = None


class AgentRequest(_Contract, Generic[_Payload]):
    """A request context paired with an operation-specific payload."""

    context: RequestContext
    payload: _Payload


class SuccessResponse(_Contract, Generic[_Payload]):
    """A successful result, correlated with its originating request."""

    status: Literal["success"] = "success"
    request_id: _NonBlankString
    session_id: _NonBlankString | None = None
    data: _Payload


class AgentError(_Contract):
    """A client-safe error; messages must not contain internal diagnostics."""

    code: ErrorCode
    message: _NonBlankString
    retryable: bool = False


class ErrorResponse(_Contract):
    """A failed result with no success data."""

    status: Literal["error"] = "error"
    request_id: _NonBlankString
    session_id: _NonBlankString | None = None
    error: AgentError
