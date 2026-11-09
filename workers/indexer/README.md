# Athena lecture indexer

Turns a lecture recording into topic-labelled clips: time ranges over the one
recording, each with a topic, title and summary. Output (`clips.json`) matches the
frontend's `LectureClip` type and converts to the agent's `VideoSegment`.

```
recording → 1 audio (ffmpeg) → 2 transcript (Whisper) → 3 numbered lines
          → 4 LLM proposes line ranges per topic → 5 cleanup → clips.json
```

The LLM returns line ranges, never timestamps; code converts lines to times, so
clip times always come from the transcript.

## Setup and test

Run from `workers/indexer/`:

```sh
uv sync
uv run pytest
```

Tests run offline. Put recordings in `data/` (gitignored). Never commit
recordings, audio or transcripts.

## Index a recording

```sh
uv run index-lecture data/<recording>.mp4 --topics topics/cse5alg.json \
  --title "Week 2: Insertion sort" --recording-id alg-w2 --llm-model <openai-model-id>
```

Runs every step and writes `data/<recording>/clips.json` (for the frontend) and
`video_segments.json` (for the agent). Each step is cached, so reruns only redo
what changed. Needs `OPENAI_API_KEY`, and `OPENAI_MODEL` unless `--llm-model` is given,
in the environment or the repo's `.env`.

## Transcribe only

```sh
uv run python -m athena_indexer.transcribe data/<recording>.mp4 --model small
```

Writes `data/<recording>/transcript.json`. Each 10-minute chunk is cached in
`data/<recording>/chunks/`, so rerunning after an interruption resumes. Whisper
runs locally on the CPU; the model downloads once on first use.

## Status

- [x] 1. Data formats (`models.py`)
- [x] 2. Audio extraction and chunking (`audio.py`)
- [x] 3. Local Whisper transcription (`transcribe.py`)
- [x] 4. Transcript → numbered lines (`lines.py`)
- [x] 5. LLM segmentation (`segment.py`)
- [x] 6. Boundary cleanup (`cleanup.py`)
- [x] 7. `index-lecture` command (`pipeline.py`)
