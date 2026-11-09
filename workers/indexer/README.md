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

## Status

- [x] 1. Data formats (`models.py`)
- [ ] 2. Audio extraction and chunking
- [ ] 3. Local Whisper transcription
- [ ] 4. Transcript → numbered lines
- [ ] 5. LLM segmentation
- [ ] 6. Boundary cleanup
- [ ] 7. `index-lecture` command
