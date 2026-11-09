"""FastAPI integration boundary with injected dependencies and trusted host identity."""

import inspect
from typing import Annotated, Awaitable, Callable, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import TypeAdapter, ValidationError

from ._schema import Contract, NonBlankString
from .contracts import AgentError, ErrorResponse, RequestContext, SuccessResponse
from .conversation import ConversationError, InMemoryConversationStore
from .llm import LLM, MockLLM
from .memory import LearningMemoryStore, LearnerScopedMemory
from .api_models import StartSession, MessageSubmission, ContinueSubmission, MaterialSubmission, ContentRequest
from .assessment_models import AnswerSubmission
from .orchestrator_models import LearningMessageResult, LearningView
from .learning import LearningActivity
from .activities import ClientCapabilities
from .content import ContentService
from .knowledge import KnowledgeService
from .retrieval import Retriever, RetrievalRequest, RetrievalResult
from .orchestrator import LearningOrchestrator

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
        session_id=getattr(getattr(request.state, 'context', None), 'session_id', None) or request.path_params.get('session_id'),
        error=AgentError(code=code, message=message, retryable=retryable),
    )
    return JSONResponse(status_code=status, content=response.model_dump(mode='json'))


def create_app(store: LearningMemoryStore, llm: LLM, *, learner_resolver: IdentityResolver = host_learner, retriever_resolver: Callable[[RequestContext], Retriever] | None = None) -> FastAPI:
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
        return error_response(request, error.code, str(error), 404 if error.code == 'session_not_found' else 400)

    @app.get('/health', response_model=SuccessResponse[Health])
    async def health(request: Request):
        return SuccessResponse[Health](request_id=request.state.request_id, data=Health())

    def orchestrator(context: RequestContext):
        return LearningOrchestrator(LearnerScopedMemory(store, context.learner_id), llm)

    @app.post('/sessions', response_model=SuccessResponse[LearningActivity])
    async def start_session(payload: StartSession, request: Request, context: Annotated[RequestContext, Depends(request_context)]):
        context = context.model_copy(update={'session_id': payload.session_id})
        request.state.context = context
        activity = await orchestrator(context).start(context, payload.goal, difficulty=payload.difficulty, materials=payload.materials, capabilities=payload.capabilities)
        return SuccessResponse[LearningActivity](request_id=context.request_id, session_id=context.session_id, data=activity)

    @app.get('/sessions/{session_id}/resume', response_model=SuccessResponse[LearningActivity])
    async def resume_session(session_id: NonBlankString, context: Annotated[RequestContext, Depends(request_context)]):
        activity = orchestrator(context).resume(context)
        return SuccessResponse[LearningActivity](request_id=context.request_id, session_id=context.session_id, data=activity)

    @app.post('/sessions/{session_id}/messages', response_model=SuccessResponse[LearningMessageResult])
    async def submit_message(session_id: NonBlankString, payload: MessageSubmission, context: Annotated[RequestContext, Depends(request_context)]):
        result = await orchestrator(context).message(context, payload.text)
        return SuccessResponse[LearningMessageResult](request_id=context.request_id, session_id=context.session_id, data=result)

    @app.post('/sessions/{session_id}/answers', response_model=SuccessResponse[LearningActivity])
    async def submit_answer(session_id: NonBlankString, payload: AnswerSubmission, context: Annotated[RequestContext, Depends(request_context)]):
        activity = await orchestrator(context).answer(context, payload.answer, hint_used=payload.hint_used)
        return SuccessResponse[LearningActivity](request_id=context.request_id, session_id=context.session_id, data=activity)

    @app.post('/sessions/{session_id}/continue', response_model=SuccessResponse[LearningActivity])
    async def continue_session(session_id: NonBlankString, payload: ContinueSubmission, context: Annotated[RequestContext, Depends(request_context)]):
        activity = await orchestrator(context).continue_learning(context, payload.activity_id)
        return SuccessResponse[LearningActivity](request_id=context.request_id, session_id=context.session_id, data=activity)

    @app.get('/sessions/{session_id}', response_model=SuccessResponse[LearningView])
    async def session_view(session_id: NonBlankString, context: Annotated[RequestContext, Depends(request_context)]):
        view = orchestrator(context).view(context)
        return SuccessResponse[LearningView](request_id=context.request_id, session_id=context.session_id, data=view)

    @app.put('/sessions/{session_id}/materials', response_model=SuccessResponse[RetrievalResult])
    async def select_materials(session_id: NonBlankString, payload: MaterialSubmission, context: Annotated[RequestContext, Depends(request_context)]):
        result = await KnowledgeService(LearnerScopedMemory(store, context.learner_id)).supply(context, payload.result, source_ids=payload.source_ids, max_results=payload.max_results)
        return SuccessResponse[RetrievalResult](request_id=context.request_id, session_id=context.session_id, data=result)

    @app.post('/sessions/{session_id}/retrieval', response_model=SuccessResponse[RetrievalResult])
    async def retrieve_materials(session_id: NonBlankString, payload: RetrievalRequest, context: Annotated[RequestContext, Depends(request_context)]):
        retriever = retriever_resolver(context) if retriever_resolver is not None else None
        result = await KnowledgeService(LearnerScopedMemory(store, context.learner_id), retriever).retrieve(context, payload.query, source_ids=payload.source_ids, max_results=payload.max_results)
        return SuccessResponse[RetrievalResult](request_id=context.request_id, session_id=context.session_id, data=result)

    @app.put('/sessions/{session_id}/capabilities', response_model=SuccessResponse[ClientCapabilities])
    async def update_capabilities(session_id: NonBlankString, payload: ClientCapabilities, context: Annotated[RequestContext, Depends(request_context)]):
        await ContentService(LearnerScopedMemory(store, context.learner_id), llm).set_capabilities(context, payload)
        return SuccessResponse[ClientCapabilities](request_id=context.request_id, session_id=context.session_id, data=payload)

    @app.post('/sessions/{session_id}/content', response_model=SuccessResponse[LearningActivity])
    async def generate_content(session_id: NonBlankString, payload: ContentRequest, context: Annotated[RequestContext, Depends(request_context)]):
        activity = await ContentService(LearnerScopedMemory(store, context.learner_id), llm).generate(context, payload.concept_id)
        return SuccessResponse[LearningActivity](request_id=context.request_id, session_id=context.session_id, data=activity)

    return app


def create_demo_app() -> FastAPI:
    """Runnable offline service shell; hosts inject configured adapters for learning."""
    return create_app(InMemoryConversationStore(), MockLLM([]))
