import asyncio
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

from athena_agent.evaluation import evaluate_fixture
from athena_agent.runner import run_text_journey


def fixture():
    return json.loads((Path(__file__).parent / 'fixtures/text_journey.json').read_text())


def test_full_mock_text_journey_is_repeatable_and_targets_gap():
    first = asyncio.run(run_text_journey(fixture()))
    assert first['passed'] and len(first['transcript']) == 5
    assert first == asyncio.run(evaluate_fixture(fixture()))
    assert first['transcript'][1]['kind'] == 'explanation'
    assert first['transcript'][-1]['mastered'] == 1
    assert 'criteria' not in json.dumps(first)


def test_runner_fails_a_behavioral_expectation():
    data = fixture()
    data['expected_mastered'] = [1] * 5
    result = asyncio.run(run_text_journey(data))
    assert not result['passed'] and not result['checks']['mastery_progress']


def test_runner_cli_emits_transcript_and_success_exit():
    result = subprocess.run([sys.executable, '-m', 'athena_agent.runner', str(Path(__file__).parent / 'fixtures/text_journey.json')], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['passed']
