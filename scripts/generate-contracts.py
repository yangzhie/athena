"""Deterministic API/schema generation. Never reads credentials or calls a model."""
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as temp:
    os.environ.update(ATHENA_DB=temp + '/host.db', ATHENA_AGENT_DB=temp + '/agent.db', ATHENA_TUTOR='placeholder', OPENAI_API_KEY='', OPENAI_MODEL='')
    from athena_api.app import create_app
    schema = create_app().openapi()
    target = ROOT / 'packages/shared'
    target.mkdir(exist_ok=True)
    (target / 'openapi.json').write_text(json.dumps(schema, indent=2, sort_keys=True) + '\n')
    subprocess.run(['npx', '--no-install', 'openapi-typescript', str(target / 'openapi.json'), '-o', str(target / 'api.ts')], cwd=ROOT, check=True)
    subprocess.run(['npm', 'run', 'build:headless', '-w', '@athena/playground'], cwd=ROOT, check=True)
    engine = subprocess.run(['node', str(ROOT / 'packages/playground/dist/headless.mjs')], input='{"kind":"contract"}', text=True, capture_output=True, check=True)
    catalog = json.loads(engine.stdout)['data']
    definitions = {}
    for name in ['Scene', 'Action', 'Check', 'CanvasSnapshot', 'ToolCall', 'ToolResult', 'RunResult', 'Observation']:
        result = subprocess.run(['npx', '--no-install', 'ts-json-schema-generator', '--path', 'packages/playground/src/contracts.ts', '--type', name, '--no-type-check'], cwd=ROOT, capture_output=True, text=True, check=True)
        definitions[name] = json.loads(result.stdout)
    catalog['schemas'] = definitions
    (target / 'playground.json').write_text(json.dumps(catalog, indent=2, sort_keys=True) + '\n')
