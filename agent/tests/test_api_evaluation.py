import asyncio
import json
from pathlib import Path

import pytest

from athena_agent.evaluation import evaluate_fixture
from athena_agent.live_evaluation import evaluate_live_quality, main
from athena_agent.llm import MockLLM


def test_full_mock_api_journey_and_bundled_resilience():
    fixture = json.loads((Path(__file__).parent / 'fixtures/api_journey.json').read_text())
    result = asyncio.run(evaluate_fixture(fixture))
    assert result['passed'], result
    assert len(result['resilience']) == 3
    assert result == asyncio.run(evaluate_fixture(fixture))


def test_live_harness_requires_explicit_opt_in_before_configuration(monkeypatch):
    import athena_agent.openai_llm as adapter
    def forbidden():
        pytest.fail('Live configuration must not be read without opt-in.')
    monkeypatch.setattr(adapter.OpenAISettings, 'from_env', forbidden)
    with pytest.raises(SystemExit) as error:
        main(['nonexistent-fixture.json'])
    assert error.value.code == 2


def test_live_quality_harness_uses_mock_provider_and_rubric_without_paid_calls():
    fixture = json.loads((Path(__file__).parent / 'fixtures/live_quality.json').read_text())
    mock = MockLLM([{'text': 'Compare adjacent values, swapping only when out of order.'},
                    {'accurate': True, 'targets_gap': True, 'single_focused_unit': True, 'engaging_and_actionable': True, 'rationale': 'Targets the pair selection error.'}])
    result = asyncio.run(evaluate_live_quality(mock, fixture['scenarios'][0]))
    assert result['passed'] and len(mock.calls) == 2
    assert 'expected_correction' in mock.calls[1].messages[1].content


def test_live_quality_negative_rubric_fails_the_evaluation():
    fixture = json.loads((Path(__file__).parent / 'fixtures/live_quality.json').read_text())
    mock = MockLLM([{'text': 'An inaccurate explanation.'},
                    {'accurate': False, 'targets_gap': False, 'single_focused_unit': True, 'engaging_and_actionable': False, 'rationale': 'Does not correct adjacent pair selection.'}])
    result = asyncio.run(evaluate_live_quality(mock, fixture['scenarios'][0]))
    assert not result['passed'] and not result['checks']['accurate']
