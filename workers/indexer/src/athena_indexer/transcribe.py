"""Step 3: audio → timed transcript, chunk by chunk, with a resumable cache.

Speech-to-text sits behind the `Transcriber` protocol: local Whisper today,
a cloud API or the lecture-capture system's captions later, a fake in tests.
"""

import json
import time
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Protocol

from .audio import CHUNK_S, OVERLAP_S, Chunk, cut_chunk, extract_audio, plan_chunks, probe_duration, read_samples
from .models import Transcript, TranscriptSegment


class Transcriber(Protocol):
    #: Identifies the engine and settings; cached chunks are reused only when it matches.
    name: str

    def transcribe(self, audio: Path) -> list[tuple[float, float, str]]:
        """(start_s, end_s, text) per spoken segment, times relative to the start of `audio`."""
        ...


class WhisperTranscriber:
    """Local Whisper via faster-whisper. Runs on CPU by default; no audio leaves the machine.

    Model sizes: tiny, base, small, medium, large-v3. Bigger is more accurate and slower.
    The model is downloaded once (to ~/.cache/huggingface) on first use.
    """

    def __init__(self, model_size: str = "small", *, device: str = "cpu", compute_type: str = "int8", language: str | None = "en"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.name = f"faster-whisper:{model_size}:{compute_type}:{language or 'auto'}"
        self._model = None

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel  # heavy import; only when actually transcribing

            self._model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
        return self._model

    def transcribe(self, audio: Path) -> list[tuple[float, float, str]]:
        segments, _info = self._load().transcribe(
            read_samples(audio),  # decode with ffmpeg rather than faster-whisper's PyAV call
            language=self.language,
            vad_filter=True,  # skip silence: faster, and fewer made-up words in quiet parts
            beam_size=5,
        )
        return [(s.start, s.end, s.text.strip()) for s in segments]


ProgressFn = Callable[[int, int, float], None]
"""Called after each chunk with (chunks_done, chunks_total, seconds_taken_for_this_chunk)."""


def stitch(chunks: list[Chunk], per_chunk: list[list[tuple[float, float, str]]], duration_s: float) -> list[TranscriptSegment]:
    """Join chunk transcripts into one, with absolute times.

    Each chunk keeps only segments whose midpoint it owns, so speech in the
    overlap between two chunks appears exactly once.
    """
    out: list[TranscriptSegment] = []
    for chunk, segments in zip(chunks, per_chunk, strict=True):
        for start, end, text in segments:
            a = min(max(0.0, chunk.start_s + start), duration_s)
            b = min(max(0.0, chunk.start_s + end), duration_s)
            if b <= a or not text.strip() or not chunk.owns((a + b) / 2):
                continue
            out.append(TranscriptSegment(start_s=a, end_s=b, text=text.strip()))
    out.sort(key=lambda s: s.start_s)
    return out


def _chunk_cache(workdir: Path, chunk: Chunk) -> Path:
    return workdir / "chunks" / f"chunk-{chunk.index:03d}.json"


def _load_cached(path: Path, chunk: Chunk, engine: str):
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    if data.get("engine") != engine or data.get("chunk") != asdict(chunk):
        return None  # different model or chunk plan: redo it
    return [tuple(s) for s in data["segments"]]


def transcribe_recording(
    recording: Path,
    workdir: Path,
    transcriber: Transcriber,
    *,
    recording_id: str | None = None,
    chunk_s: float = CHUNK_S,
    overlap_s: float = OVERLAP_S,
    on_progress: ProgressFn | None = None,
) -> Transcript:
    """Extract audio, transcribe it chunk by chunk, and write `workdir/transcript.json`.

    Each finished chunk is cached in `workdir/chunks/`, so an interrupted run
    resumes where it stopped. Cut chunk audio is deleted once transcribed.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    audio = extract_audio(recording, workdir / "audio.flac")
    duration = probe_duration(audio)
    chunks = plan_chunks(duration, chunk_s, overlap_s)

    per_chunk = []
    for chunk in chunks:
        cache = _chunk_cache(workdir, chunk)
        segments = _load_cached(cache, chunk, transcriber.name)
        started = time.monotonic()
        if segments is None:
            part = cut_chunk(audio, chunk, workdir / "chunks" / f"chunk-{chunk.index:03d}.flac", overwrite=True)
            segments = transcriber.transcribe(part)
            tmp = cache.with_suffix(".partial.json")
            tmp.write_text(json.dumps({"engine": transcriber.name, "chunk": asdict(chunk), "segments": segments}))
            tmp.replace(cache)
            part.unlink(missing_ok=True)
        per_chunk.append(segments)
        if on_progress:
            on_progress(chunk.index + 1, len(chunks), time.monotonic() - started)

    transcript = Transcript(
        recording_id=recording_id or recording.stem,
        duration_s=duration,
        language=getattr(transcriber, "language", None),
        segments=stitch(chunks, per_chunk, duration),
    )
    (workdir / "transcript.json").write_text(transcript.model_dump_json(indent=2))
    return transcript


def main(argv: list[str] | None = None) -> None:
    """Transcribe one recording: python -m athena_indexer.transcribe <recording> [--model small]."""
    import argparse

    p = argparse.ArgumentParser(description="Transcribe a lecture recording with local Whisper.")
    p.add_argument("recording", type=Path)
    p.add_argument("--out", type=Path, help="working folder (default: data/<recording name>/)")
    p.add_argument("--model", default="small", help="tiny, base, small, medium, large-v3 (default: small)")
    args = p.parse_args(argv)

    workdir = args.out or Path("data") / args.recording.stem
    began = time.monotonic()

    def progress(done: int, total: int, took: float) -> None:
        print(f"chunk {done}/{total} done in {took:.0f}s (elapsed {time.monotonic() - began:.0f}s)", flush=True)

    t = transcribe_recording(args.recording, workdir, WhisperTranscriber(args.model), on_progress=progress)
    words = sum(len(s.text.split()) for s in t.segments)
    print(f"{len(t.segments)} segments, {words} words, {t.duration_s / 60:.1f} min of audio "
          f"in {(time.monotonic() - began) / 60:.1f} min → {workdir / 'transcript.json'}")


if __name__ == "__main__":
    main()
