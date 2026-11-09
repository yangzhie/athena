import json
import shutil
import subprocess

import pytest

from athena_indexer.audio import plan_chunks
from athena_indexer.transcribe import stitch, transcribe_recording

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


class FakeTranscriber:
    """Says "word at <absolute second>" every 2 s, so stitched output is predictable."""

    name = "fake:v1"
    language = "en"

    def __init__(self, chunk_starts):
        self.chunk_starts = iter(chunk_starts)
        self.calls = 0

    def transcribe(self, audio):
        self.calls += 1
        offset = next(self.chunk_starts)
        duration = float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(audio)],
            capture_output=True, text=True, check=True,
        ).stdout)
        out, t = [], 0.0
        while t + 1 <= duration:
            out.append((t, t + 1, f"word at {round(offset + t)}"))
            t += 2
        return out


# --- Stitching (pure) -----------------------------------------------------------------


def test_stitch_drops_overlap_duplicates_and_offsets_times():
    chunks = plan_chunks(20.0, chunk_s=10, overlap_s=4)  # chunk 0: 0–12, chunk 1: 8–20; boundary at 10
    per_chunk = [
        [(0.0, 2.0, "a"), (9.0, 9.6, "owned by 0"), (10.5, 11.5, "dup in 0")],
        [(1.0, 1.6, "dup in 1"), (2.5, 3.5, "owned by 1"), (10.0, 11.0, "end")],
    ]
    out = stitch(chunks, per_chunk, 20.0)
    assert [s.text for s in out] == ["a", "owned by 0", "owned by 1", "end"]
    assert out[2].start_s == pytest.approx(10.5)  # 8 + 2.5


def test_stitch_skips_blank_and_zero_length_and_clamps_to_duration():
    [chunk] = plan_chunks(10.0, chunk_s=600, overlap_s=5)
    out = stitch([chunk], [[(1.0, 1.0, "zero"), (2.0, 3.0, "  "), (9.0, 12.0, "past end")]], 10.0)
    assert [(s.text, s.end_s) for s in out] == [("past end", 10.0)]


# --- End to end with ffmpeg and a fake engine --------------------------------------


@pytest.fixture
def recording(tmp_path):
    path = tmp_path / "lecture.mp4"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=25", str(path)],
        check=True,
    )
    return path


@needs_ffmpeg
def test_transcribes_resumes_and_writes_transcript(recording, tmp_path):
    workdir = tmp_path / "work"
    starts = [c.start_s for c in plan_chunks(25.0, chunk_s=10, overlap_s=2)]
    progress = []

    fake = FakeTranscriber(starts)
    t = transcribe_recording(recording, workdir, fake, chunk_s=10, overlap_s=2, on_progress=lambda d, n, _: progress.append((d, n)))
    assert fake.calls == 3
    assert progress == [(1, 3), (2, 3), (3, 3)]

    texts = [s.text for s in t.segments]
    assert len(texts) == len(set(texts)), "overlap must not duplicate speech"
    assert all(a.start_s <= b.start_s for a, b in zip(t.segments, t.segments[1:]))
    assert json.loads((workdir / "transcript.json").read_text())["recording_id"] == "lecture"
    assert not list((workdir / "chunks").glob("*.flac")), "chunk audio is cleaned up"

    # Second run: everything comes from the cache.
    again = FakeTranscriber(starts)
    t2 = transcribe_recording(recording, workdir, again, chunk_s=10, overlap_s=2)
    assert again.calls == 0
    assert t2 == t


@needs_ffmpeg
def test_cache_is_ignored_when_engine_changes(recording, tmp_path):
    starts = [c.start_s for c in plan_chunks(25.0, chunk_s=10, overlap_s=2)]
    transcribe_recording(recording, tmp_path / "w", FakeTranscriber(starts), chunk_s=10, overlap_s=2)
    other = FakeTranscriber(starts)
    other.name = "fake:v2"
    transcribe_recording(recording, tmp_path / "w", other, chunk_s=10, overlap_s=2)
    assert other.calls == 3
