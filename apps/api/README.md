# apps/api

Athena's API service: a FastAPI modular monolith. It starts with the **SRS**
module (spaced repetition per unit); the tutor orchestrator, auth and other
modules join later.

## Setup and test

Run from `apps/api/`:

```sh
uv sync
uv run pytest
```

## SRS design

- A unit's **bank** holds **items**. An item is one idea to remember, with several
  **variants**: different wordings, framings or input data for the same question.
- **FSRS** (the `fsrs` library) schedules each student's **card** per item.
- Each review shows a variant the student hasn't seen recently, and never the one
  they last got wrong. When an item runs out of fresh variants, the LLM
  rephrases one live; live variants are saved and marked pending for a lecturer to check.
- A wording a student got wrong is never shown to that student again.
- Cards and review logs are private to the student (see AGENTS.md, Privacy).

## Status

- [x] 1. Service scaffold and SRS data formats (`srs/models.py`)
- [x] 2. Scheduler and variant rotation (`srs/scheduler.py`)
- [ ] 3. Storage (SQLite) and API routes
- [ ] 4. Starter banks for CSE5ALG and CSE5DMI
- [ ] 5. Review screen in the web app
- [ ] 6. Live rephrasing when variants run out
- [ ] 7. Bank generator from unit material
