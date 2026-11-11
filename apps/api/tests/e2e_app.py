"""Explicit browser-test server. Synthetic model fixtures; never a production mode."""
import json
from pathlib import Path

from athena_api.app import create_app
from athena_api.sessions.agent_tutor import ScriptedDemoTutor
from athena_api.sessions.service import SessionService
from athena_api.sessions.store import SqliteSessionStore
from athena_api.spaces.service import StudySpaces
from athena_api.srs.service import SrsService
from athena_api.srs.store import SqliteStore
from athena_api.lectures.service import LectureService
from athena_api.lectures.store import SqliteLectureStore
import os

CODE = {'id': 'code-example', 'title': 'Python multiplication', 'goal': 'Predict 6 times 7', 'objects': [
    {'id': 'code', 'type': 'code-graph', 'title': 'Python', 'provenance': 'concept',
     'config': {'language': 'python', 'source': 'print(6 * 7)', 'probeValues': ['0']}}],
    'checks': [{'id': 'ran', 'objectId': 'code', 'on': ['runCompleted'], 'when': {'field': 'ok', 'op': 'eq', 'value': True},
                'verdict': 'correct', 'explain': 'Explain the output independently.', 'completesGoal': True}]}

class PlaygroundFixture:
    async def generate(self, messages, response_model):
        if response_model.__name__ == 'SceneDraft':
            return response_model(scene_json=json.dumps(CODE), explanation='Test experiment')
        if response_model.__name__ == 'ToolDraft':
            return response_model(explanation='Let’s inspect the state.', calls_json='[{"name":"get_canvas_state","input":{}}]')
        return response_model(text='Experiment is ready. Explain why the output is 42.')

path = Path(os.environ['ATHENA_DB'])
tutor = ScriptedDemoTutor(Path(__file__).parents[3] / 'agent/tests/fixtures/api_journey.json')
tutor.mode = 'ai'  # Only this explicit test factory; class-level mode remains demo.
tutor.llm = PlaygroundFixture()
app = create_app(spaces=StudySpaces(path), sessions=SessionService(SqliteSessionStore(path), tutor=tutor),
                 srs=SrsService(SqliteStore(path)), lectures=LectureService(SqliteLectureStore(path)))
tutor.material = None

# Real extraction worker, started only by this test factory.
import subprocess
import atexit
worker = subprocess.Popen([str(Path(__file__).parents[1] / '.venv/bin/python'), '-m', 'athena_api.materials.worker'])
atexit.register(worker.terminate)
execution = subprocess.Popen([str(Path(__file__).parents[1] / '.venv/bin/python'), '-m', 'athena_api.execution.worker'])
atexit.register(execution.terminate)
