"""Durable processing worker. No extraction/transcription runs in API requests."""
import argparse
import json
import math
import os
import shlex
import signal
import subprocess
import threading
import time
from pathlib import Path

from ..env import load_dotenv
from ..lectures.service import LectureService
from ..lectures.store import SqliteLectureStore
from ..spaces.service import StudySpaces
from .extract import ExtractionError, extract
from .store import Materials


def index_recording(row, materials, lectures):
    try:
        probe = subprocess.run(['ffprobe', '-protocol_whitelist', 'file,pipe', '-v', 'error',
                                '-show_entries', 'format=duration', '-of', 'json', row['storage_path']],
                               capture_output=True, text=True, timeout=20, check=True)
        duration = float(json.loads(probe.stdout)['format']['duration'])
        if not math.isfinite(duration) or not 0 < duration <= 14400:
            raise ValueError()
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        raise ExtractionError('The recording is unreadable, exceeds four hours, or FFmpeg is unavailable.') from None
    work = materials.root / 'index' / row['id']
    work.mkdir(parents=True, exist_ok=True)
    with materials.lock:
        topics = [dict(id=r[0], title=r[1]) for r in materials.db.execute('SELECT id,title FROM offering_topics WHERE offering_id=?', (row['offering_id'],))]
    if not topics:
        topics = [dict(id='lecture', title=Path(row['filename']).stem)]
    # Existing indexer accepts id/name topic fields (see its Topic contract).
    topics = [dict(id=t['id'], name=t['title']) for t in topics]
    topic_file = work / 'topics.json'
    topic_file.write_text(json.dumps({'topics': topics}))
    root = Path(__file__).resolve().parents[5]
    command = shlex.split(os.environ.get('ATHENA_INDEXER_COMMAND', f'uv run --project {shlex.quote(str(root / "workers/indexer"))} index-lecture'))
    command += [row['storage_path'], '--topics', str(topic_file), '--out', str(work), '--recording-id', row['id'],
                '--offering', row['offering_id'], '--title', row['filename'],
                '--whisper-model', os.environ.get('ATHENA_WHISPER_MODEL', 'small')]
    process = None
    try:
        # Discard subprocess output: provider diagnostics may include course text.
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        process.wait(timeout=int(os.environ.get('ATHENA_PROCESSING_TIMEOUT', '3600')))
        if process.returncode:
            raise ExtractionError('Recording indexing failed. Check indexer dependencies and model configuration, then retry; cached transcription is retained.')
        if not materials.heartbeat(row):
            raise ExtractionError('Processing lease expired; another worker is recovering this recording.')
        data = json.loads((work / 'clips.json').read_text())
        # Force server-owned source identity and media path, never trust returned paths.
        data.update(recordingId=row['id'], offeringId=row['offering_id'], media=os.path.relpath(row['storage_path'], work))
        lectures.import_indexer_file(data, offering_id=row['offering_id'], base_dir=work)
    except subprocess.TimeoutExpired:
        raise ExtractionError('Recording indexing exceeded its time limit. Retry to resume cached work.') from None
    except (FileNotFoundError, json.JSONDecodeError):
        raise ExtractionError('Recording indexer is unavailable or returned no usable result. Install/configure the indexing worker, then retry.') from None
    finally:
        if process and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()


def process_one(materials, lectures, recording_indexer=index_recording):
    row = materials.claim()
    if row is None:
        return False
    stop = threading.Event()
    def heartbeat():
        while not stop.wait(15):
            materials.heartbeat(row)
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        if row['kind'] == 'recording':
            recording_indexer(row, materials, lectures)
            materials.finish(row)
        else:
            materials.finish(row, passages=extract(Path(row['storage_path']), row['suffix']))
    except ExtractionError as error:
        materials.finish(row, error=str(error))
    except Exception:
        materials.finish(row, error='Processing failed. Check the worker installation and retry.')
    finally:
        stop.set()
        thread.join()
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true', help='Process at most one queued job.')
    args = parser.parse_args()
    load_dotenv()
    path = Path(os.environ.get('ATHENA_DB', 'data/athena.db'))
    spaces = StudySpaces(path)
    lecture_store = SqliteLectureStore(path)
    materials = Materials(spaces, os.environ.get('ATHENA_MATERIAL_ROOT', 'data/materials'))
    def terminate(_signal, _frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, terminate)
    try:
        while True:
            processed = process_one(materials, LectureService(lecture_store))
            if args.once:
                break
            if not processed:
                time.sleep(2)
    except KeyboardInterrupt:
        pass  # The job lease expires; another worker can resume the cached work.
    finally:
        lecture_store.close()
        spaces.close()


if __name__ == '__main__':
    main()
