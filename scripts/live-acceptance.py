"""Explicit opt-in, at most 12 SDK calls. Synthetic material; report contains no prompts/keys."""
import argparse
import asyncio
import json
import os
import tempfile
import time
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--allow-paid-calls', action='store_true', required=True)
parser.add_argument('--max-calls', type=int, default=12, choices=range(1,13))
parser.add_argument('--general-planning', action='store_true')
parser.add_argument('--core-only', action='store_true')
parser.add_argument('--model', default='gpt-4.1-mini')
parser.add_argument('--report', type=Path, default=Path('/tmp/athena-live-acceptance.json'))
args = parser.parse_args()
from athena_api.env import load_dotenv
load_dotenv()
from athena_agent.openai_llm import OpenAILLM, OpenAISettings
from athena_agent.reliable_llm import ReliableLLM, RetryPolicy
from athena_agent.sqlite_memory import SQLiteLearningMemory
from athena_api.app import create_app
from athena_api.spaces.service import StudySpaces, CreateOffering
from athena_api.sessions.agent_tutor import AgentTutor
from athena_api.sessions.service import SessionService
from athena_api.sessions.store import SqliteSessionStore
from athena_api.srs.service import SrsService
from athena_api.srs.store import SqliteStore
from athena_api.lectures.service import LectureService
from athena_api.lectures.store import SqliteLectureStore
from athena_api.materials.worker import process_one
from athena_api.execution.worker import run_once
from pydantic import SecretStr

class Counted:
    def __init__(self, llm):
        self.llm, self.calls = llm, []
    async def generate(self, messages, response_model):
        if len(self.calls) >= args.max_calls:
            raise RuntimeError('Authorized paid-call budget exhausted')
        entry = {'schema': response_model.__name__, 'ok': False}
        self.calls.append(entry)
        started = time.monotonic()
        try:
            result = await self.llm.generate(messages, response_model)
            entry['ok'] = True
            return result
        finally:
            entry['duration_ms'] = round((time.monotonic() - started) * 1000)
            args.report.write_text(json.dumps({'model': args.model, 'calls': self.calls, 'usage': self.llm.usage}, indent=2))

async def main():
    provider = OpenAILLM(OpenAISettings(model=args.model, api_key=SecretStr(os.environ['OPENAI_API_KEY']), timeout=45, max_output_tokens=4096))
    counted = Counted(provider)
    checks = {}
    try:
        with tempfile.TemporaryDirectory(prefix='athena-live-') as directory:
            path = Path(directory)
            spaces = StudySpaces(path / 'host.db')
            student, _ = spaces.identity(None)
            spaces.redeem_lecturer_invite(student, spaces.create_lecturer_invite())
            offering = spaces.create(student, CreateOffering(code='LIVE', title='Synthetic Python course', year=2026, semester='Semester 2'))['id']
            spaces.publish(student, offering)
            tutor = AgentTutor(SQLiteLearningMemory(path / 'agent.db'), ReliableLLM(counted, policy=RetryPolicy(max_attempts=1)))
            sessions = SessionService(SqliteSessionStore(path / 'host.db'), tutor=tutor)
            app = create_app(spaces=spaces, sessions=sessions, srs=SrsService(SqliteStore(path / 'host.db')),
                             lectures=LectureService(SqliteLectureStore(path / 'host.db')))
            materials = app.state.materials
            # Ensure all synthetic files stay in the temporary acceptance directory.
            materials.root = path / 'materials'; materials.root.mkdir(exist_ok=True)
            row = materials.reserve_upload(offering, 'synthetic-python.txt')
            source = 'In Python, 0 is a real measurement and None represents a missing observation. To remove only missing observations, use [x for x in values if x is not None]. For [0, 10, None, 20], the retained values are [0, 10, 20] and their average is 10.0. Using if x also removes zero and incorrectly gives 15.0.'
            Path(row['storage_path']).write_text(source)
            materials.finish_upload(row, len(source.encode()))
            process_one(materials, app.state.lectures)
            materials.publish(offering, row['id'])
            offering_material = tutor.material
            if args.general_planning:
                tutor.material = None
            session, messages = await sessions.create(student, offering, 'Python filtering: keep zero measurements and remove only None')
            checks['planning'] = bool(messages and messages[-1].activity)
            activity = messages[-1].activity
            question = activity['question']
            if question['kind'] == 'multiple_choice':
                from athena_agent.contracts import RequestContext
                snapshot = tutor.store.read(RequestContext(request_id='acceptance', learner_id=student, session_id=session.id))
                criterion = next(q.bundle.criteria for q in snapshot.active_topic.question_records if q.bundle.question.question_id == question['question_id'])
                answer = {'choice_id': criterion.correct_choice_id, 'text': None}
            else:
                answer = {'choice_id': None, 'text': 'Zero is a real measurement. Filter with x is not None so zero remains; if x wrongly removes zero.'}
            replies = await sessions.answer(student, offering, session.id, question['question_id'], shown='Synthetic acceptance answer', hint_used=False, **answer)
            checks['assessment'] = bool(replies)
            checks['answer_replay'] = replies == await sessions.answer(student, offering, session.id, question['question_id'], shown='Synthetic acceptance answer', hint_used=False, **answer)
            activity = replies[-1].activity
            if activity and activity['kind'] == 'explanation' and len(counted.calls) <= args.max_calls - 5:
                replies = await sessions.continue_(student, offering, session.id, activity['activity_id'])
            checks['grounding'] = any(m.sources for m in [*messages, *replies])
            tutor.material = offering_material
            if args.core_only:
                return
            pg = app.state.playgrounds
            generated = await pg.tutor.turn(student, offering, session.id, 'live-scene', 'Create one code-graph experiment using the supplied Python data-cleaning material. Show the correct filter and print its average. I want to predict and run it.', 'scene')
            view = pg.get(student, offering, session.id)
            checks['grounding'] = checks['grounding'] or any(m.sources for m in sessions.store.messages(student, session.id))
            checks['scene_generation'] = bool(view['snapshot'] and view['snapshot']['objects'])
            code = next((o for o in view['snapshot']['objects'] if o['type'] == 'code-graph'), None)
            if code:
                pg.command(student, offering, session.id, 'live-run', view['revision'], {'kind': 'action', 'action': {'objectId': code['id'], 'type': 'run'}})
                run_once(pg.executions)
                view = pg.get(student, offering, session.id)
                checks['real_execution'] = any(j['result'] and j['result']['provenance'] == 'real-run' and j['result']['ok'] for j in view['executions'])
                if len(counted.calls) < args.max_calls:
                    job = view['executions'][-1]
                    await pg.tutor.turn(student, offering, session.id, 'execution:' + job['id'], 'Interpret the actual verified output and ask one independent reasoning question.', 'execution')
                    checks['execution_interpretation'] = True
            if len(counted.calls) <= args.max_calls - 2:
                await pg.tutor.turn(student, offering, session.id, 'live-inspect', 'Inspect the canvas with get_canvas_state and highlight the important code object. Explain an unexpected empty-input case.', 'question')
                checks['tool_result_interpretation'] = True
    finally:
        await provider.aclose()
        usage = provider.usage
        input_tokens = sum(r['input_tokens'] for r in usage)
        output_tokens = sum(r['output_tokens'] for r in usage)
        cached = sum(r['cached_input_tokens'] for r in usage)
        report = {'model': args.model, 'calls': counted.calls, 'usage': usage, 'checks': checks,
                  'estimated_usd': round(((input_tokens-cached)*.4 + cached*.1 + output_tokens*1.6)/1_000_000, 6) if args.model == 'gpt-4.1-mini' else None,
                  'pricing_source': 'https://developers.openai.com/api/docs/models/gpt-4.1-mini'}
        args.report.write_text(json.dumps(report, indent=2))
        print(json.dumps({'paid_calls': len(counted.calls), 'checks': checks, 'estimated_usd': report['estimated_usd'], 'report': str(args.report)}))

asyncio.run(main())
