import json
import shutil
import subprocess

import pytest

from athena_indexer.audio import (
    SAMPLE_RATE,
    AudioError,
    cut_chunk,
    extract_audio,
    plan_chunks,
    probe_duration,
)

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


# --- Chunk planning (pure) ------------------------------------------------------------


def test_short_recording_is_one_chunk_owning_everything():
    [c] = plan_chunks(120.0, chunk_s=600, overlap_s=5)
    assert (c.start_s, c.end_s) == (0.0, 120.0)
    assert c.owns(0.0) and c.owns(119.9) and c.owns(125.0)


def test_two_hour_lecture_chunks_overlap_and_cover_once():
    duration = 2 * 3600 + 7.5
    chunks = plan_chunks(duration, chunk_s=600, overlap_s=5)
    assert len(chunks) == 13
    assert chunks[0].start_s == 0.0 and chunks[-1].end_s == duration
    for a, b in zip(chunks, chunks[1:]):
        assert a.end_s - b.start_s == pytest.approx(5.0)  # overlap
        assert a.own_end_s == b.own_start_s  # ownership is contiguous
    # Every moment is owned by exactly one chunk.
    for t in [0.0, 599.9, 600.0, 3600.0, duration - 0.1]:
        assert sum(c.owns(t) for c in chunks) == 1


def test_exact_multiple_does_not_create_an_empty_chunk():
    chunks = plan_chunks(1200.0, chunk_s=600, overlap_s=5)
    assert len(chunks) == 2
    assert all(c.duration_s > 0 for c in chunks)


def test_invalid_plans():
    assert plan_chunks(0.0) == []
    with pytest.raises(ValueError):
        plan_chunks(100.0, chunk_s=10, overlap_s=5)


# --- ffmpeg -----------------------------------------------------------------------------


@pytest.fixture
def recording(tmp_path):
    """A 25 s stereo 44.1 kHz tone with a video track, standing in for a lecture."""
    path = tmp_path / "lecture.mkv"
    subprocess.run(
        [
            "ffmpeg", "-nostdin", "-v", "error",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=25:sample_rate=44100",
            "-f", "lavfi", "-i", "color=c=black:s=64x64:d=25",
            "-ac", "2", "-shortest", str(path),
        ],
        check=True,
    )
    return path


def _streams(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)["streams"]


@needs_ffmpeg
def test_extract_audio_is_16k_mono_without_video(recording, tmp_path):
    out = extract_audio(recording, tmp_path / "audio.flac")
    [stream] = _streams(out)
    assert stream["codec_type"] == "audio"
    assert int(stream["sample_rate"]) == SAMPLE_RATE
    assert stream["channels"] == 1
    assert probe_duration(out) == pytest.approx(25.0, abs=0.1)
    assert not list(tmp_path.glob("*.partial*"))


@needs_ffmpeg
def test_extract_audio_reuses_existing_output(recording, tmp_path):
    out = extract_audio(recording, tmp_path / "audio.flac")
    mtime = out.stat().st_mtime_ns
    extract_audio(recording, out)
    assert out.stat().st_mtime_ns == mtime


@needs_ffmpeg
def test_cut_chunks_have_planned_lengths(recording, tmp_path):
    audio = extract_audio(recording, tmp_path / "audio.flac")
    chunks = plan_chunks(probe_duration(audio), chunk_s=10, overlap_s=2)
    assert len(chunks) == 3
    for c in chunks:
        part = cut_chunk(audio, c, tmp_path / f"chunk-{c.index:03d}.flac")
        assert probe_duration(part) == pytest.approx(c.duration_s, abs=0.1)


@needs_ffmpeg
def test_errors_are_readable(tmp_path):
    with pytest.raises(AudioError, match="not found"):
        extract_audio(tmp_path / "missing.mp4", tmp_path / "a.flac")
    bad = tmp_path / "not-media.mp4"
    bad.write_text("hello")
    with pytest.raises(AudioError, match="ffprobe failed"):
        probe_duration(bad)
