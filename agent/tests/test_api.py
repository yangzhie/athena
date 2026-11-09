import asyncio

import httpx

from athena_agent.api import create_app, create_demo_app
from athena_agent._schema import Contract, NonBlankString
from athena_agent.conversation import InMemoryConversationStore
from athena_agent.llm import MockLLM


def request(app, method, path, **kwargs):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            return await client.request(method, path, **kwargs)
    return asyncio.run(run())


def test_service_health_and_request_correlation():
    app = create_demo_app()
    response = request(app, 'GET', '/health', headers={'x-request-id': 'host-request'})
    assert response.status_code == 200
    assert response.json() == {'status': 'success', 'request_id': 'host-request', 'session_id': None, 'data': {'service': 'athena-agent', 'ready': True}}
    assert request(app, 'GET', '/health', headers={'x-request-id': ' '}).status_code == 422


def test_validation_errors_use_safe_envelopes_not_raw_payloads():
    app = create_app(InMemoryConversationStore(), MockLLM([]))
    class Probe(Contract):
        text: NonBlankString
    @app.post('/probe')
    async def probe(payload: Probe):
        return payload
    response = request(app, 'POST', '/probe', json={'text': 'private', 'extra': 'secret-value'})
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'invalid_request'
    assert 'secret-value' not in response.text
    assert response.json()['request_id']


def test_start_resume_use_host_identity_and_hide_private_records():
    from .test_orchestrator import one_concept_responses
    store = InMemoryConversationStore()
    mock = MockLLM(one_concept_responses())
    app = create_app(store, mock, learner_resolver=lambda request: app.state.trusted_learner)
    app.state.trusted_learner = 'host-learner'
    response = request(app, 'POST', '/sessions', json={'session_id': 's', 'goal': 'Comparisons'})
    assert response.status_code == 200, response.text
    assert response.json()['data']['kind'] == 'question'
    assert response.json()['session_id'] == 's'
    assert 'correct_choice_id' not in response.text and 'criteria' not in response.text
    resumed = request(app, 'GET', '/sessions/s/resume')
    assert resumed.json()['data'] == response.json()['data'] and len(mock.calls) == 4
    app.state.trusted_learner = 'other'
    foreign = request(app, 'GET', '/sessions/s/resume')
    assert foreign.status_code == 404 and foreign.json()['error']['code'] == 'session_not_found'


def test_start_rejects_client_identity_and_missing_host_without_model_calls():
    mock = MockLLM([])
    app = create_app(InMemoryConversationStore(), mock)
    assert request(app, 'POST', '/sessions', json={'session_id': 's', 'goal': 'Sorting'}).status_code == 400
    bound = create_app(InMemoryConversationStore(), mock, learner_resolver=lambda request: 'trusted')
    response = request(bound, 'POST', '/sessions', json={'session_id': 's', 'goal': 'Sorting', 'learner_id': 'forged'})
    assert response.status_code == 422 and mock.calls == []


def test_api_answers_teach_continue_and_preserve_idempotency():
    from .test_orchestrator import one_concept_responses, OPEN
    mock = MockLLM([*one_concept_responses(), {'misconceptions': [], 'prerequisite_gaps': []}, {'text': 'Compare adjacent values.'}, OPEN])
    app = create_app(InMemoryConversationStore(), mock, learner_resolver=lambda request: 'trusted')
    first = request(app, 'POST', '/sessions', json={'session_id': 's', 'goal': 'Sorting'}).json()['data']
    payload = {'answer': {'kind': 'multiple_choice', 'question_id': first['question']['question_id'], 'selected_choice_id': 'b'}}
    teaching = request(app, 'POST', '/sessions/s/answers', json=payload)
    assert teaching.status_code == 200 and teaching.json()['data']['kind'] == 'explanation'
    replay = request(app, 'POST', '/sessions/s/answers', json=payload)
    assert replay.json()['data'] == teaching.json()['data']
    followup = request(app, 'POST', '/sessions/s/continue', json={'activity_id': teaching.json()['data']['activity_id']})
    assert followup.status_code == 200 and followup.json()['data']['question']['kind'] == 'open_ended'
    malformed = request(app, 'POST', '/sessions/s/answers', json={'answer': {'kind': 'text', 'question_id': 'q', 'text': ' '}})
    assert malformed.status_code == 422


def test_message_clarification_preserves_current_question_and_topic_switch_replans():
    from .test_orchestrator import one_concept_responses
    mock = MockLLM([*one_concept_responses(), {'intent': 'clarification'}, {'text': 'Compare neighbours.'}, {'intent': 'topic_change', 'new_goal': 'Graphs'}, {'text': 'We will explore graphs.'}, *one_concept_responses()])
    store = InMemoryConversationStore()
    app = create_app(store, mock, learner_resolver=lambda request: 'trusted')
    first = request(app, 'POST', '/sessions', json={'session_id': 's', 'goal': 'Sorting'}).json()['data']
    clarification = request(app, 'POST', '/sessions/s/messages', json={'text': 'Explain that.'})
    assert clarification.status_code == 200 and clarification.json()['data']['activity'] == first
    assert first['question']['prompt'] in mock.calls[5].messages[1].content
    changed = request(app, 'POST', '/sessions/s/messages', json={'text': 'Switch to graphs.'})
    assert changed.status_code == 200 and changed.json()['data']['activity']['kind'] == 'question'
    from athena_agent.contracts import RequestContext
    session = store.read(RequestContext(request_id='check', learner_id='trusted', session_id='s'))
    assert session.active_topic.learning_state.goal == 'Graphs' and len(session.archived_topics) == 1
    assert session.active_topic.learning_state.mastery == []


def test_session_view_returns_consistent_public_state_progress_and_feedback():
    from .test_orchestrator import one_concept_responses
    from athena_agent.contracts import RequestContext
    mock = MockLLM([*one_concept_responses(), {'misconceptions': [], 'prerequisite_gaps': []}, {'text': 'Compare neighbours.'}])
    store = InMemoryConversationStore()
    app = create_app(store, mock, learner_resolver=lambda request: 'trusted')
    first = request(app, 'POST', '/sessions', json={'session_id': 's', 'goal': 'Sorting'}).json()['data']
    initial = request(app, 'GET', '/sessions/s').json()['data']
    assert initial['activity'] == first and initial['progress']['next_step'] == 'answer'
    assert initial['latest_feedback'] is None
    request(app, 'POST', '/sessions/s/answers', json={'answer': {'kind': 'multiple_choice', 'question_id': first['question']['question_id'], 'selected_choice_id': 'b'}})
    context = RequestContext(request_id='check', learner_id='trusted', session_id='s')
    before = store.read(context)
    response = request(app, 'GET', '/sessions/s')
    data = response.json()['data']
    assert data['activity']['kind'] == 'explanation' and data['learning_state']['phase'] == 'teach'
    assert data['progress']['next_step'] == 'continue'
    assert data['latest_feedback']['content']['outcome'] == 'incorrect'
    assert store.read(context) == before
    assert 'question_records' not in response.text and 'correct_choice_id' not in response.text


def test_api_accepts_materials_and_context_bound_retrieval():
    from .test_orchestrator import one_concept_responses
    from .test_knowledge import material
    from athena_agent.retrieval import MockRetriever
    mock = MockLLM(one_concept_responses())
    retriever = MockRetriever([material()])
    resolved = []
    def resolver(context):
        resolved.append((context.learner_id, context.session_id))
        return retriever
    app = create_app(InMemoryConversationStore(), mock, learner_resolver=lambda request: 'trusted', retriever_resolver=resolver)
    request(app, 'POST', '/sessions', json={'session_id': 's', 'goal': 'Sorting'})
    supplied = request(app, 'PUT', '/sessions/s/materials', json={'result': material().model_dump(mode='json')})
    assert supplied.status_code == 200 and supplied.json()['data'] == material().model_dump(mode='json')
    fetched = request(app, 'POST', '/sessions/s/retrieval', json={'query': 'Adjacent comparisons'})
    assert fetched.status_code == 200 and resolved == [('trusted', 's')]
    assert retriever.calls[0].query == 'Adjacent comparisons'


def test_api_capabilities_drive_structured_content_generation():
    from .test_orchestrator import one_concept_responses
    mock = MockLLM([*one_concept_responses(), {'format': 'diagram', 'rationale': 'Shows comparison.'}, {'text': 'Compare adjacent values.', 'parameters': {'kind': 'diagram', 'nodes': [{'node_id': 'a', 'label': 'Compare'}]}}])
    app = create_app(InMemoryConversationStore(), mock, learner_resolver=lambda request: 'trusted')
    request(app, 'POST', '/sessions', json={'session_id': 's', 'goal': 'Sorting'})
    assert request(app, 'PUT', '/sessions/s/capabilities', json={'formats': ['diagram']}).status_code == 200
    content = request(app, 'POST', '/sessions/s/content', json={'concept_id': 'comparison'})
    assert content.status_code == 200 and content.json()['data']['kind'] == 'rich'
    assert request(app, 'PUT', '/sessions/s/capabilities', json={'formats': ['html']}).status_code == 422


def test_api_dependency_model_and_unknown_errors_are_safe_and_correlated():
    from athena_agent.llm import DependencyError, InvalidOutputError
    from athena_agent.reliable_llm import ReliableLLM, RetryPolicy
    cases = [(DependencyError('secret provider body', retryable=True), 503, 'dependency_unavailable', True), (InvalidOutputError(), 502, 'invalid_model_output', True)]
    for failure, status, code, retryable in cases:
        mock = ReliableLLM(MockLLM([failure]), policy=RetryPolicy(max_attempts=1))
        app = create_app(InMemoryConversationStore(), mock, learner_resolver=lambda request: 'trusted')
        response = request(app, 'POST', '/sessions', json={'session_id': 's', 'goal': 'Sorting'}, headers={'x-request-id': 'r-safe'})
        assert response.status_code == status and response.json()['error']['code'] == code
        assert response.json()['error']['retryable'] == retryable
        assert response.json()['request_id'] == 'r-safe' and response.json()['session_id'] == 's'
        assert 'secret provider body' not in response.text
    def broken_resolver(request):
        raise RuntimeError('unrelated secret traceback')
    app = create_app(InMemoryConversationStore(), MockLLM([]), learner_resolver=broken_resolver)
    response = request(app, 'GET', '/sessions/s')
    assert response.status_code == 500 and response.json()['error']['code'] == 'internal_error'
    assert 'traceback' not in response.text


def test_api_missing_retrieval_and_bad_routes_use_envelopes():
    from .test_orchestrator import one_concept_responses
    app = create_app(InMemoryConversationStore(), MockLLM(one_concept_responses()), learner_resolver=lambda request: 'trusted')
    request(app, 'POST', '/sessions', json={'session_id': 's', 'goal': 'Sorting'})
    response = request(app, 'POST', '/sessions/s/retrieval', json={'query': 'Sorting'})
    assert response.status_code == 503 and response.json()['error']['code'] == 'dependency_unavailable'
    assert request(app, 'GET', '/unknown').json()['status'] == 'error'
    blank = request(app, 'GET', '/sessions/%20/resume')
    assert blank.status_code in {400, 422} and blank.json()['session_id'] is None


def test_openapi_documents_error_envelopes_and_validated_request_examples():
    from athena_agent.api_models import StartSession, MessageSubmission, ContinueSubmission, MaterialSubmission, ContentRequest
    from athena_agent.assessment_models import AnswerSubmission
    app = create_demo_app()
    schema = request(app, 'GET', '/openapi.json').json()
    for model in [StartSession, MessageSubmission, ContinueSubmission, MaterialSubmission, ContentRequest, AnswerSubmission]:
        examples = model.model_json_schema()['examples']
        for example in examples:
            assert model.model_validate(example)
        assert schema['components']['schemas'][model.__name__]['examples'] == examples
    responses = schema['paths']['/sessions']['post']['responses']
    assert responses['422']['content']['application/json']['schema']['$ref'].endswith('/ErrorResponse')
    assert responses['503']['content']['application/json']['schema']['$ref'].endswith('/ErrorResponse')
    assert 'learner_id' not in schema['components']['schemas']['StartSession']['properties']
