"""Offline API behavior evaluations using explicit mock adapters."""

import httpx
from pydantic import TypeAdapter

from .api import create_app
from .contracts import ErrorResponse, SuccessResponse
from .conversation import InMemoryConversationStore
from .learning import LearningActivity
from .llm import DependencyError, MockLLM
from .reliable_llm import ReliableLLM, RetryPolicy
from .retrieval import MockRetriever


async def evaluate_api_journey(fixture: dict) -> dict:
    store = InMemoryConversationStore()
    mock = MockLLM(fixture['responses'])
    retriever = MockRetriever([fixture['materials']])
    llm = ReliableLLM(mock, policy=RetryPolicy(max_attempts=1))
    app = create_app(store, llm, learner_resolver=lambda request: app.state.learner,
                     retriever_resolver=lambda context: retriever)
    app.state.learner = 'fixture'
    activity_adapter = TypeAdapter(SuccessResponse[LearningActivity])
    checks = {}
    phases = []
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://offline') as client:
        async def activity_request(path, body):
            response = await client.post(path, json=body)
            response.raise_for_status()
            return activity_adapter.validate_json(response.content).data
        activity = await activity_request('/sessions', {'session_id': 's', 'goal': fixture['goal']})
        phases.append((await client.get('/sessions/s')).json()['data']['learning_state']['phase'])
        retrieval = await client.post('/sessions/s/retrieval', json={'query': fixture['goal']})
        checks['retrieval_adapter'] = retrieval.status_code == 200 and len(retriever.calls) == 1
        for index, turn in enumerate(fixture['turns']):
            if turn['kind'] == 'continue':
                activity = await activity_request('/sessions/s/continue', {'activity_id': activity.activity_id})
            else:
                answer = ({'kind': 'multiple_choice', 'selected_choice_id': turn['value']} if turn['kind'] == 'choice'
                          else {'kind': 'text', 'text': turn['value']})
                answer['question_id'] = activity.question.question_id
                payload = {'answer': answer}
                activity = await activity_request('/sessions/s/answers', payload)
                if index == 0:
                    calls = len(mock.calls)
                    replay = await activity_request('/sessions/s/answers', payload)
                    checks['idempotent_answer'] = replay == activity and len(mock.calls) == calls
            view = (await client.get('/sessions/s')).json()['data']
            phases.append(view['learning_state']['phase'])
        checks['adaptive_phases'] = phases == fixture['expected_phases']
        checks['mastery_completion'] = view['progress']['complete'] and view['progress']['mastered_count'] == 1
        resumed = activity_adapter.validate_json((await client.get('/sessions/s/resume')).content).data
        checks['resume'] = resumed == activity
        await client.put('/sessions/s/capabilities', json={'formats': ['diagram']})
        rich = await activity_request('/sessions/s/content', {'concept_id': 'bubble-sort'})
        checks['structured_content'] = rich.kind == 'rich' and rich.parameters.kind == 'diagram' and bool(rich.sources)
        await client.put('/sessions/s/capabilities', json={'formats': []})
        text = await activity_request('/sessions/s/content', {'concept_id': 'bubble-sort'})
        checks['text_alternative'] = text.kind == 'explanation' and bool(text.sources)
        malformed = await client.post('/sessions/s/answers', json={'answer': {'kind': 'text', 'question_id': 'x', 'text': ' '}})
        checks['invalid_request_contract'] = malformed.status_code == 422 and ErrorResponse.model_validate_json(malformed.content).error.code == 'invalid_request'
        app.state.learner = 'foreign'
        foreign = await client.get('/sessions/s')
        checks['learner_isolation'] = foreign.status_code == 404 and ErrorResponse.model_validate_json(foreign.content).error.code == 'session_not_found'
    results = []
    for case in fixture['resilience_cases']:
        responses = [DependencyError('Private dependency diagnostics', retryable=value.get('retryable', False)) if value.get('__error__') else value for value in case['responses']]
        provider = MockLLM(responses)
        memory = InMemoryConversationStore()
        candidate = create_app(memory, ReliableLLM(provider, policy=RetryPolicy(max_attempts=2, initial_delay=0.0)), learner_resolver=lambda request: 'fixture')
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=candidate), base_url='http://offline') as client:
            response = await client.post('/sessions', json={'session_id': 's', 'goal': fixture['goal']})
        passed = response.status_code == case['expected_status'] and len(provider.calls) == case['expected_calls']
        if response.status_code != 200:
            parsed = ErrorResponse.model_validate_json(response.content)
            passed = passed and 'Private dependency' not in parsed.error.message and not memory._sessions
        results.append({'scenario': case['name'], 'passed': passed})
    return {'scenario': fixture['name'], 'passed': all(checks.values()) and all(item['passed'] for item in results), 'checks': checks, 'resilience': results}
