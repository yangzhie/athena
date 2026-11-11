"""Step 2: recording → 16 kHz mono audio, split into overlapping chunks.

Whisper works on 16 kHz mono, so converting once up front keeps every later
step fast and small. Chunks let transcription resume after a failure and
report progress on long lectures. Uses the ffmpeg and ffprobe command-line tools.
"""

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

SAMPLE_RATE = 16_000
CHUNK_S = 600.0  # 10 minutes
OVERLAP_S = 5.0  # so words cut at a boundary appear whole in one chunk


class AudioError(RuntimeError):
    """ffmpeg/ffprobe failed or isn't installed."""


def _run(cmd: list[str]) -> str:
    if shutil.which(cmd[0]) is None:
        raise AudioError(f"{cmd[0]} is not installed or not on PATH")
    cmd = [cmd[0], "-protocol_whitelist", "file,pipe", *cmd[1:]]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        raise AudioError(f"{cmd[0]} exceeded its processing limit") from None
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-5:])
        raise AudioError(f"{cmd[0]} failed: {tail}")
    return proc.stdout


def probe_duration(path: Path) -> float:
    """Length of a media file in seconds."""
    out = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)])
    try:
        return float(json.loads(out)["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError):
        raise AudioError(f"could not read the duration of {path.name}") from None


def extract_audio(src: Path, dest: Path, *, overwrite: bool = False) -> Path:
    """Write the recording's audio as 16 kHz mono FLAC (lossless, about half the size of WAV).

    Skips the work if `dest` already exists and is newer than `src`, so reruns resume.
    """
    if not src.exists():
        raise AudioError(f"recording not found: {src}")
    if not overwrite and dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".partial" + dest.suffix)
    _run([
        "ffmpeg", "-nostdin", "-y", "-v", "error",
        "-i", str(src),
        "-vn",  # drop video
        "-ac", "1", "-ar", str(SAMPLE_RATE),
        "-c:a", "flac",
        str(tmp),
    ])
    tmp.replace(dest)  # only a complete file ever has the final name
    return dest


@dataclass(frozen=True)
class Chunk:
    """A slice of the audio to transcribe.

    [start_s, end_s) is what gets cut, including overlap with neighbours.
    [own_start_s, own_end_s) is the part this chunk is responsible for: when
    stitching, keep only speech whose midpoint falls in it, so overlap isn't duplicated.
    """

    index: int
    start_s: float
    end_s: float
    own_start_s: float
    own_end_s: float

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s

    def owns(self, absolute_s: float) -> bool:
        return self.own_start_s <= absolute_s < self.own_end_s


def plan_chunks(duration_s: float, chunk_s: float = CHUNK_S, overlap_s: float = OVERLAP_S) -> list[Chunk]:
    """Split `duration_s` into chunks of about `chunk_s`, overlapping by `overlap_s`.

    Ownership boundaries sit in the middle of each overlap, and together cover
    the whole recording exactly once.
    """
    if duration_s <= 0:
        return []
    if chunk_s <= 2 * overlap_s:
        raise ValueError("chunk_s must be more than twice overlap_s")

    boundaries = [0.0]
    while boundaries[-1] + chunk_s < duration_s:
        boundaries.append(boundaries[-1] + chunk_s)
    boundaries.append(duration_s)

    chunks = []
    last = len(boundaries) - 2
    for i, (a, b) in enumerate(zip(boundaries, boundaries[1:])):
        start = max(0.0, a - overlap_s / 2)
        end = min(duration_s, b + overlap_s / 2)
        own_end = float("inf") if i == last else b  # the last chunk owns anything past the end
        chunks.append(Chunk(index=i, start_s=start, end_s=end, own_start_s=a, own_end_s=own_end))
    return chunks


def read_samples(path: Path):
    """Decode audio to a float32 numpy array at 16 kHz mono, the input Whisper expects.

    Decoding with the ffmpeg CLI keeps us independent of PyAV's Python API, which
    changes between releases.
    """
    import numpy as np  # installed with faster-whisper

    if shutil.which("ffmpeg") is None:
        raise AudioError("ffmpeg is not installed or not on PATH")
    proc = subprocess.run(
        ["ffmpeg", "-protocol_whitelist", "file,pipe", "-nostdin", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-"],
        capture_output=True,
    )
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.decode(errors="replace").strip().splitlines()[-5:])
        raise AudioError(f"ffmpeg failed: {tail}")
    return np.frombuffer(proc.stdout, dtype=np.float32)


def cut_chunk(audio: Path, chunk: Chunk, dest: Path, *, overwrite: bool = False) -> Path:
    """Write one chunk of `audio` to `dest` (FLAC). Skips existing files unless `overwrite`."""
    if not overwrite and dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".partial" + dest.suffix)
    _run([
        "ffmpeg", "-nostdin", "-y", "-v", "error",
        "-ss", f"{chunk.start_s:.3f}", "-t", f"{chunk.duration_s:.3f}",
        "-i", str(audio),
        "-c:a", "flac",
        str(tmp),
    ])
    tmp.replace(dest)
    return dest
