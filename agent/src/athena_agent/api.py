"""FastAPI integration boundary with injected dependencies and trusted host identity."""

import inspect
from typing import Awaitable, Callable, Literal
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import TypeAdapter, ValidationError

from ._schema import Contract, NonBlankString
from .contracts import AgentError, ErrorResponse, RequestContext, SuccessResponse
from .conversation import ConversationError, InMemoryConversationStore
from .llm import LLM, MockLLM
from .memory import LearningMemoryStore

IdentityResolver = Callable[[Request], str | Awaitable[str]]


class Health(Contract):
    service: Literal['athena-agent'] = 'athena-agent'
    ready: Literal[True] = True


def host_learner(request: Request) -> str:
    """Read identity placed by trusted host middleware, never a client header/body."""
    identity = getattr(request.state, 'learner_id', None)
    try:
        return TypeAdapter(NonBlankString).validate_python(identity)
    except ValidationError:
        raise ConversationError('Trusted learner identity is required.') from None


async def request_context(request: Request) -> RequestContext:
    identity = request.app.state.learner_resolver(request)
    if inspect.isawaitable(identity):
        identity = await identity
    try:
        context = RequestContext(request_id=request.state.request_id, learner_id=identity,
                                 session_id=request.path_params.get('session_id'))
    except ValidationError:
        raise ConversationError('Trusted learner identity and session context are required.') from None
    request.state.context = context
    return context


def error_response(request: Request, code: str, message: str, status: int, *, retryable: bool = False) -> JSONResponse:
    response = ErrorResponse(
        request_id=getattr(request.state, 'request_id', str(uuid4())),
        session_id=request.path_params.get('session_id'),
        error=AgentError(code=code, message=message, retryable=retryable),
    )
    return JSONResponse(status_code=status, content=response.model_dump(mode='json'))


def create_app(store: LearningMemoryStore, llm: LLM, *, learner_resolver: IdentityResolver = host_learner) -> FastAPI:
    app = FastAPI(title='Athena Agent', version='0.1.0')
    app.state.store = store
    app.state.llm = llm
    app.state.learner_resolver = learner_resolver

    @app.middleware('http')
    async def correlate(request: Request, call_next):
        request.state.request_id = str(uuid4())
        supplied = request.headers.get('x-request-id')
        if supplied is not None:
            try:
                request.state.request_id = TypeAdapter(NonBlankString).validate_python(supplied)
            except ValidationError:
                return error_response(request, 'invalid_request', 'Request identifier must be nonblank.', 422)
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError):
        return error_response(request, 'invalid_request', 'The request does not match the API contract.', 422)

    @app.exception_handler(ConversationError)
    async def invalid_operation(request: Request, error: ConversationError):
        return error_response(request, error.code, str(error), 400)

    @app.get('/health', response_model=SuccessResponse[Health])
    async def health(request: Request):
        return SuccessResponse[Health](request_id=request.state.request_id, data=Health())

    return app


def create_demo_app() -> FastAPI:
    """Runnable offline service shell; hosts inject configured adapters for learning."""
    return create_app(InMemoryConversationStore(), MockLLM([]))
