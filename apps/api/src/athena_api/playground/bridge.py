import json
import os
import subprocess
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException

BUNDLE = Path(__file__).resolve().parents[5] / 'packages/playground/dist/headless.mjs'


def invoke(body):
    payload = json.dumps(body, ensure_ascii=False)
    if len(payload.encode()) > 2 * 1024 * 1024:
        raise HTTPException(413, 'Playground state exceeds 2 MiB')
    try:
        # This runs only bundled trusted TypeScript. Python source remains inert JSON.
        result = subprocess.run(['node', '--max-old-space-size=128', str(BUNDLE)], input=payload,
                                text=True, capture_output=True, timeout=8,
                                env={'PATH': os.environ.get('PATH', '/usr/bin:/bin')})
        if result.returncode or len(result.stdout) > 2 * 1024 * 1024:
            raise ValueError()
        output = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        raise HTTPException(503, 'Playground engine is unavailable. Build the headless bundle and retry.') from None
    if not output.get('ok'):
        raise HTTPException(422, str(output.get('error', 'Invalid Playground operation'))[:2000])
    return output['data']


@lru_cache(maxsize=1)
def catalog():
    runtime = invoke({'kind': 'contract'})
    schema_file = BUNDLE.parents[2] / 'shared/playground.json'
    try:
        generated = json.loads(schema_file.read_text())
        if generated['catalog_version'] != runtime['catalog_version']:
            raise ValueError()
        runtime['schemas'] = generated['schemas']
    except (OSError, ValueError, KeyError):
        raise HTTPException(503, 'Playground schemas unavailable; regenerate shared contracts.') from None
    return runtime


def transition(checkpoint, command=None):
    return invoke({'checkpoint': checkpoint, 'command': command})
