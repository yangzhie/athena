"""Validation and serialization checks for the public agent envelopes."""

import json

import pytest
from pydantic import ValidationError

from athena_agent.contracts import (
    AgentError,
    AgentRequest,
    ErrorResponse,
    RequestContext,
    SuccessResponse,
)


@pytest.mark.parametrize("session_id", [None, "session-1"])
def test_envelopes_round_trip(session_id):
    context = RequestContext(
        request_id="request-1", learner_id="learner-1", session_id=session_id
    )
    envelopes = [
        AgentRequest[dict[str, str]](context=context, payload={"topic": "Sorting"}),
        SuccessResponse[dict[str, str]](
            request_id=context.request_id, session_id=session_id, data={"text": "Ready"}
        ),
        ErrorResponse(
            request_id=context.request_id,
            session_id=session_id,
            error=AgentError(code="dependency_unavailable", message="Try again.", retryable=True),
        ),
    ]

    for envelope in envelopes:
        assert type(envelope).model_validate_json(envelope.model_dump_json()) == envelope


def test_optional_session_ids_and_defaults():
    context = RequestContext(request_id="r", learner_id="l")
    success = SuccessResponse[str](request_id="r", data="Ready")
    error = AgentError(code="internal_error", message="Unable to complete request.")
    failure = ErrorResponse(request_id="r", error=error)

    assert context.session_id is success.session_id is failure.session_id is None
    assert success.status == "success"
    assert failure.status == "error"
    assert error.retryable is False


def test_identifiers_are_preserved_without_trimming():
    context = RequestContext(request_id=" r ", learner_id=" l ", session_id=" s ")

    assert context.model_dump() == {
        "request_id": " r ", "learner_id": " l ", "session_id": " s "
    }


@pytest.mark.parametrize("field", ["request_id", "learner_id", "session_id"])
@pytest.mark.parametrize("invalid", ["", " \t\n", 123, False])
def test_context_rejects_invalid_identifiers(field, invalid):
    data = {"request_id": "r", "learner_id": "l", "session_id": "s", field: invalid}

    with pytest.raises(ValidationError):
        RequestContext.model_validate(data)


@pytest.mark.parametrize("field", ["request_id", "learner_id"])
def test_context_requires_correlation_and_identity(field):
    data = {"request_id": "r", "learner_id": "l"}
    del data[field]

    with pytest.raises(ValidationError):
        RequestContext.model_validate(data)


@pytest.mark.parametrize("invalid", ["", " \n", 123, None])
def test_error_requires_nonblank_message(invalid):
    with pytest.raises(ValidationError):
        AgentError(code="invalid_request", message=invalid)


@pytest.mark.parametrize("invalid", ["true", 1, None])
def test_retryable_requires_boolean(invalid):
    with pytest.raises(ValidationError):
        AgentError(code="internal_error", message="Failed.", retryable=invalid)


@pytest.mark.parametrize("code", [
    "invalid_request", "session_not_found", "dependency_unavailable",
    "invalid_model_output", "internal_error",
])
def test_supported_error_codes(code):
    assert AgentError(code=code, message="Failed.").code == code


def test_unknown_error_code_is_rejected():
    with pytest.raises(ValidationError):
        AgentError(code="unknown", message="Failed.")


@pytest.mark.parametrize("model,data", [
    (RequestContext, {"request_id": "r", "learner_id": "l"}),
    (AgentRequest[str], {"context": {"request_id": "r", "learner_id": "l"}, "payload": "Hello"}),
    (SuccessResponse[str], {"request_id": "r", "data": "Ready"}),
    (AgentError, {"code": "invalid_request", "message": "Failed."}),
    (ErrorResponse, {"request_id": "r", "error": {"code": "internal_error", "message": "Failed."}}),
])
def test_unexpected_fields_are_rejected(model, data):
    with pytest.raises(ValidationError):
        model.model_validate({**data, "unexpected": True})


def test_payload_validation_is_typed_and_strict():
    with pytest.raises(ValidationError):
        AgentRequest[dict[str, str]](
            context=RequestContext(request_id="r", learner_id="l"),
            payload={"topic": 42},
        )
    with pytest.raises(ValidationError):
        SuccessResponse[int](request_id="r", data="42")


@pytest.mark.parametrize("model,data", [
    (SuccessResponse[str], {"request_id": "r", "data": "Ready", "status": "error"}),
    (ErrorResponse, {"request_id": "r", "error": {"code": "internal_error", "message": "Failed."}, "status": "success"}),
    (SuccessResponse[str], {"request_id": "r", "data": "Ready", "error": {"code": "internal_error", "message": "Failed."}}),
    (ErrorResponse, {"request_id": "r", "error": {"code": "internal_error", "message": "Failed."}, "data": "Ready"}),
])
def test_success_and_error_cannot_be_mixed(model, data):
    with pytest.raises(ValidationError):
        model.model_validate(data)


def test_nested_context_rejects_extra_fields():
    with pytest.raises(ValidationError):
        AgentRequest[str].model_validate({
            "context": {"request_id": "r", "learner_id": "l", "extra": True},
            "payload": "Hello",
        })


def test_concrete_envelopes_generate_json_schema():
    request_schema = AgentRequest[dict[str, str]].model_json_schema()
    success_schema = SuccessResponse[list[str]].model_json_schema()
    error_schema = ErrorResponse.model_json_schema()

    assert request_schema["additionalProperties"] is False
    assert request_schema["properties"]["payload"]["additionalProperties"] == {"type": "string"}
    assert success_schema["properties"]["data"]["items"] == {"type": "string"}
    assert success_schema["properties"]["status"]["const"] == "success"
    assert error_schema["properties"]["status"]["const"] == "error"
    assert "AgentError" in error_schema["$defs"]
    json.dumps([request_schema, success_schema, error_schema])
