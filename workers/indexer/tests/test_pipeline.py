import json
import shutil
import subprocess

import pytest

from athena_indexer.models import Topic
from athena_indexer.pipeline import index_lecture, slug

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
TOPICS = [Topic(id="sort", name="Insertion Sort"), Topic(id="hash", name="Hash Tables")]


class FakeTranscriber:
    """One sentence every 3 s, mentioning sorting in the first half and hashing in the second."""

    name = "fake:v1"
    language = "en"

    def transcribe(self, audio):
        return [(t, t + 2.5, f"Sentence about {'sorting' if t < 60 else 'hashing'} number {t:.0f}.") for t in range(0, 118, 3)]


class FakeSegmenter:
    """Splits each window where the text switches from sorting to hashing."""

    name = "fake-llm:v1"

    def __init__(self):
        self.calls = 0

    def propose(self, system, user):
        self.calls += 1
        rows = [l for l in user.splitlines() if l[:1].isdigit()]
        idx = [int(r.split()[0]) for r in rows]
        switch = next((i for i, r in zip(idx, rows) if "hashing" in r), idx[-1] + 1)
        out = []
        if switch > idx[0]:
            out.append({"first_line": idx[0], "last_line": switch - 1, "topic_id": "sort", "title": "Shifting", "summary": "Insertion."})
        if switch <= idx[-1]:
            out.append({"first_line": switch, "last_line": idx[-1], "topic_id": "hash", "title": "Chaining", "summary": "Buckets."})
        return out


def test_slug():
    assert slug("2026_CSE2ALG_CSE5ALG BU 1") == "2026-cse2alg-cse5alg-bu-1"


@needs_ffmpeg
def test_index_lecture_end_to_end_and_rerun_is_cached(tmp_path):
    rec = tmp_path / "lecture.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "sine=duration=120", str(rec)], check=True)
    work = tmp_path / "work"
    seg = FakeSegmenter()
    logs = []

    result = index_lecture(rec, work, TOPICS, FakeTranscriber(), seg, recording_id="alg-w2", title="Sorting", log=logs.append)

    assert [c.topic for c in result.clips] == ["Insertion Sort", "Hash Tables"]
    assert result.clips[0].end_s <= result.clips[1].start_s
    clips = json.loads((work / "clips.json").read_text())
    assert clips["recordingId"] == "alg-w2" and len(clips["clips"]) == 2
    video = json.loads((work / "video_segments.json").read_text())
    assert video[0]["kind"] == "video" and video[0]["source_id"] == "alg-w2"
    assert any("clips →" in m for m in logs)

    seg2 = FakeSegmenter()
    again = index_lecture(rec, work, TOPICS, FakeTranscriber(), seg2, recording_id="alg-w2", title="Sorting")
    assert seg2.calls == 0
    assert again == result
