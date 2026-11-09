import asyncio

import pytest
from pydantic import ValidationError

from athena_agent.context import ContextBudget, ContextBudgetError, ContextBuilder
from athena_agent.conversation import ConversationTurn
from athena_agent.llm import InvalidOutputError, MockLLM
from athena_agent.planning import GoalInterpretation, PlanningService
from athena_agent.reliable_llm import ReliableLLM, RetryPolicy


def service(responses, **kwargs):
    mock = MockLLM(responses)
    return PlanningService(ReliableLLM(mock, policy=RetryPolicy(max_attempts=1)), **kwargs), mock


def test_clear_goal_and_clarification_continuity():
    planner, mock = service([
        {'status': 'clarification', 'clarification_question': 'Do you mean Python programming or snakes?'},
        {'status': 'resolved', 'goal': 'Learn Python programming basics'},
    ])
    ambiguous = asyncio.run(planner.interpret_goal('Teach me Python.'))
    assert ambiguous.goal is None
    turns = [ConversationTurn(user_text='Teach me Python.', assistant_text=ambiguous.clarification_question)]
    resolved = asyncio.run(planner.interpret_goal('Programming basics.', turns))
    assert resolved.goal == 'Learn Python programming basics'
    contents = [message.content for message in mock.calls[1].messages]
    assert 'Teach me Python.' in contents
    assert ambiguous.clarification_question in contents
    assert contents[-1] == 'Programming basics.'


@pytest.mark.parametrize('values', [
    {'status': 'resolved'}, {'status': 'clarification'},
    {'status': 'resolved', 'goal': 'Sorting', 'clarification_question': 'Which?'},
    {'status': 'clarification', 'goal': 'Sorting', 'clarification_question': 'Which?'},
    {'status': 'resolved', 'goal': ' '}, {'status': 'unknown', 'goal': 'Sorting'},
])
def test_invalid_goal_results(values):
    with pytest.raises(ValidationError):
        GoalInterpretation(**values)


def test_interpretation_json_roundtrip_and_schema():
    result = GoalInterpretation(status='resolved', goal='Understand Bubble Sort')
    assert GoalInterpretation.model_validate_json(result.model_dump_json()) == result
    assert GoalInterpretation.model_json_schema()['additionalProperties'] is False


def test_blank_or_oversized_request_fails_before_model_call():
    planner, mock = service([], context_builder=ContextBuilder(ContextBudget(context_window=4000)))
    with pytest.raises(ValidationError):
        asyncio.run(planner.interpret_goal(' '))
    with pytest.raises(ContextBudgetError):
        asyncio.run(planner.interpret_goal('x' * 10000))
    assert mock.calls == []


def test_invalid_interpretation_uses_shared_safe_validation():
    planner, _ = service([{'status': 'resolved'}])
    with pytest.raises(InvalidOutputError):
        asyncio.run(planner.interpret_goal('Sorting'))
