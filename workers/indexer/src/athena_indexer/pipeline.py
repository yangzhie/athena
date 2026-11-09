"""Step 7: the whole pipeline, recording → clips.json, plus the `index-lecture` command.

Every step caches its output in the working folder, so rerunning after a failure
or a change (e.g. new topics) only redoes what's needed:

    <workdir>/audio.flac           16 kHz mono audio
    <workdir>/chunks/              transcript per 10-minute chunk
    <workdir>/transcript.json      full timed transcript
    <workdir>/segments/            LLM answer per ~20-minute window
    <workdir>/clips.json           final clips (frontend LectureRecording shape)
    <workdir>/video_segments.json  the same clips as agent VideoSegment items
"""

import json
import re
import time
from collections.abc import Callable
from pathlib import Path

from .cleanup import build_clips
from .lines import to_lines
from .models import IndexResult, Topic
from .segment import SegmentModel, segment_lines
from .transcribe import Transcriber, transcribe_recording

Log = Callable[[str], None]


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "recording"


def index_lecture(
    recording: Path,
    workdir: Path,
    topics: list[Topic],
    transcriber: Transcriber,
    segmenter: SegmentModel,
    *,
    recording_id: str,
    title: str,
    offering_id: str | None = None,
    week: int | None = None,
    log: Log = lambda _msg: None,
) -> IndexResult:
    began = time.monotonic()

    def step(msg: str) -> None:
        log(f"[{time.monotonic() - began:6.0f}s] {msg}")

    step("transcribing (cached chunks are reused)")
    transcript = transcribe_recording(
        recording, workdir, transcriber, recording_id=recording_id,
        on_progress=lambda d, n, took: step(f"  chunk {d}/{n} ({took:.0f}s)"),
    )

    lines = to_lines(transcript)
    step(f"{len(transcript.segments)} transcript segments → {len(lines)} lines")

    step("segmenting by topic (cached windows are reused)")
    segments = segment_lines(
        lines, topics, segmenter, cache_dir=workdir / "segments",
        on_progress=lambda d, n: step(f"  window {d}/{n}"),
    )

    result = build_clips(
        segments, lines, topics, recording_id=recording_id, title=title, duration_s=transcript.duration_s,
        offering_id=offering_id, week=week,
    )
    (workdir / "clips.json").write_text(result.to_json())
    (workdir / "video_segments.json").write_text(json.dumps([c.to_video_segment() for c in result.clips], indent=2))
    step(f"{len(segments)} segments → {len(result.clips)} clips → {workdir / 'clips.json'}")
    return result


def main(argv: list[str] | None = None) -> None:
    import argparse

    from .env import load_dotenv
    from .lines import _clock
    from .segment import OpenAISegmentModel, load_topics
    from .transcribe import WhisperTranscriber

    p = argparse.ArgumentParser(prog="index-lecture", description="Turn a lecture recording into topic-labelled clips.")
    p.add_argument("recording", type=Path)
    p.add_argument("--topics", type=Path, required=True, help="topics JSON, e.g. topics/cse5alg.json")
    p.add_argument("--title", help="lecture title (default: the file name)")
    p.add_argument("--recording-id", help="stable id for this recording (default: from the file name)")
    p.add_argument("--offering", help="offering id the lecture belongs to, e.g. cse5alg-2026-s2")
    p.add_argument("--week", type=int, help="teaching week number")
    p.add_argument("--out", type=Path, help="working folder (default: data/<recording name>/)")
    p.add_argument("--whisper-model", default="small", help="tiny, base, small, medium, large-v3 (default: small)")
    p.add_argument("--llm-model", help="OpenAI model id (default: OPENAI_MODEL)")
    args = p.parse_args(argv)

    load_dotenv()
    workdir = args.out or Path("data") / args.recording.stem
    topics = load_topics(args.topics)
    result = index_lecture(
        args.recording, workdir, topics,
        WhisperTranscriber(args.whisper_model), OpenAISegmentModel(args.llm_model),
        recording_id=args.recording_id or slug(args.recording.stem),
        title=args.title or args.recording.stem,
        offering_id=args.offering,
        week=args.week,
        log=lambda m: print(m, flush=True),
    )
    print()
    for c in result.clips:
        print(f"{_clock(c.start_s)}–{_clock(c.end_s)}  {c.topic:<28} {c.title}")


if __name__ == "__main__":
    main()
