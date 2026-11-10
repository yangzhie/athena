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

## Run

```sh
ATHENA_DEV_STUDENT_ID=dev-student uv run uvicorn athena_api.app:create_app --factory --reload
```

Data goes to `data/athena.db` (gitignored; override with `ATHENA_DB`). Interactive
docs at http://127.0.0.1:8000/docs. `ATHENA_DEV_STUDENT_ID` stands in for SSO: every
request is that student. Without it, SRS routes return 401.

## SRS API

| Route | Does |
| --- | --- |
| `GET /units/{offering}/srs/summary` | due now, new available today, reviewed today, next due time |
| `GET /units/{offering}/srs/next` | next question, **without its answer**, or `done` with the next due time |
| `POST /units/{offering}/srs/attempts` | `{item_id, variant_id, answer}` → graded on the server, feedback; wrong answers are recorded as "again" |
| `POST /units/{offering}/srs/attempts/{id}/rating` | `{rating}` for right or short answers: hard/good/easy (short answers may also say again) |

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
- [x] 3. Storage (SQLite) and API routes (`srs/store.py`, `srs/service.py`, `srs/api.py`)
- [ ] 4. Starter banks for CSE5ALG and CSE5DMI
- [ ] 5. Review screen in the web app
- [ ] 6. Live rephrasing when variants run out
- [ ] 7. Bank generator from unit material
