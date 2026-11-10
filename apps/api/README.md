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
uv run athena-srs load-starter    # once: CSE5ALG and CSE5DMI starter banks
ATHENA_DEV_STUDENT_ID=dev-student ATHENA_DEV_LECTURER_ID=dev-lecturer uv run uvicorn athena_api.app:create_app --factory --reload
```

Live rephrasing turns on when `OPENAI_API_KEY` and `OPENAI_MODEL` are set (the
repo's `.env` is read automatically; `ATHENA_REPHRASE_MODEL` overrides the model).
Without them, items fall back to existing wordings and never repeat one the
student got wrong.

Data goes to `data/athena.db` (gitignored; override with `ATHENA_DB`). Interactive
docs at http://127.0.0.1:8000/docs. `ATHENA_DEV_STUDENT_ID` stands in for SSO: every
request is that student. Without it, SRS routes return 401.

## Generate questions from a lecture

```sh
uv run athena-srs generate \
  --clips ../../workers/indexer/data/<recording>/clips.json \
  --topics ../../workers/indexer/topics/cse5alg.json --per-clip 2
```

Drafts items from each clip's transcript with the LLM. Each must quote evidence that
appears in the transcript, use a real topic, and have 3 clearly different wordings
(multiple choice or short answer; numeric questions come from code, never the LLM).
Accepted drafts are saved **pending** and linked to their clip; students don't see
them until a lecturer approves them.

## SRS API

| Route | Does |
| --- | --- |
| `GET /units/{offering}/srs/summary` | due now, new available today, reviewed today, next due time |
| `GET /units/{offering}/srs/next` | next question, **without its answer**, or `done` with the next due time |
| `POST /units/{offering}/srs/attempts` | `{item_id, variant_id, answer}` → graded on the server, feedback; wrong answers are recorded as "again" |
| `POST /units/{offering}/srs/attempts/{id}/rating` | `{rating}` for right or short answers: hard/good/easy (short answers may also say again) |

## Lecturer: question bank review

Lecturer-only (403 otherwise). In dev, `ATHENA_DEV_LECTURER_ID` makes every request
that lecturer for every unit; real roles come from SSO. No student data is returned.

| Route | Does |
| --- | --- |
| `GET /units/{offering}/srs/bank` | every item and wording, with answers, origin and status |
| `POST …/srs/bank/items/{item}/variants/{variant}/status` | `{status: approved \| rejected \| pending}` |
| `PATCH …/srs/bank/items/{item}/variants/{variant}` | edit the wording's text and answer fields (validated; status unchanged) |
| `POST …/srs/bank/approve-pending` | `{item_ids?}` → approve every pending wording |

## Lectures

Lectures come from `workers/indexer` and are imported into the API:

```sh
uv run athena-lectures import ../../workers/indexer/data/<recording>/clips.json
```

Each clip keeps the indexer's proposal and the lecturer's review separately. Clips
start pending; re-importing a re-indexed lecture keeps the review of unchanged clips.

| Route | Who | Does |
| --- | --- | --- |
| `GET /units/{offering}/lectures` | students | approved clips only, edits applied, **no transcripts** |
| `GET /units/{offering}/lectures/review` | lecturers | every clip with status and the indexer's proposal |
| `POST …/lectures/{lecture}/clips/{clip}/status` | lecturers | `{status: approved \| rejected \| pending}` |
| `PATCH …/lectures/{lecture}/clips/{clip}` | lecturers | `{title, start_s, end_s}` rename/retime (validated; approves a pending clip) |
| `DELETE …/lectures/{lecture}/clips/{clip}/review` | lecturers | undo the decision and edits |
| `POST …/lectures/{lecture}/approve-pending` | lecturers | approve every pending clip |

Only approved clips' transcripts are used as material for the tutor.

## Sessions API

A student's learning sessions in a unit: each is one chat with a goal they chose.
All routes are scoped to the signed-in student; another student's session id gives 404.

| Route | Does |
| --- | --- |
| `GET /units/{offering}/sessions` | the student's sessions, most recent first |
| `POST /units/{offering}/sessions` | `{goal}` → new session plus the tutor's opening message |
| `GET /units/{offering}/sessions/{id}` | the session and its messages |
| `PATCH /units/{offering}/sessions/{id}` | `{title}` rename |
| `DELETE /units/{offering}/sessions/{id}` | delete the session and its messages |
| `POST /units/{offering}/sessions/{id}/messages` | `{text}` → the learner message and the tutor's reply |

| `POST /units/{offering}/sessions/{id}/answers` | `{question_id, choice_id \| text, shown}` → the learner's answer and the tutor's next messages |
| `POST /units/{offering}/sessions/{id}/continue` | `{activity_id}` → move on after a teaching step |

The tutor is the adaptive learning agent in `agent/`, used in-process
(`sessions/agent_tutor.py`). One session here is one agent session with the
student's goal: it opens with a diagnostic question, teaches, checks understanding
and adapts. Tutor messages carry the agent's learner-facing activity (`activity`),
which the web app renders as question cards and teaching steps.

`ATHENA_TUTOR` picks the tutor:

| Value | Tutor |
| --- | --- |
| *(unset)* | the agent with OpenAI if `OPENAI_API_KEY` and `OPENAI_MODEL` are set, else the placeholder |
| `placeholder` | canned text replies, no questions (e.g. while there are no API credits) |
| `demo` | the agent replaying its scripted Bubble Sort journey: try the full UI without OpenAI |

Agent memory lives in its own database, `ATHENA_AGENT_DB` (default `data/agent.db`).

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
- [x] 4. Starter banks for CSE5ALG and CSE5DMI (`srs/starter_banks.py`, `athena-srs` command)
- [ ] 5. Review screen in the web app
- [x] 6. Live rephrasing when variants run out (`srs/rephrase.py`)
- [x] 7. Bank generator from indexed lectures (`srs/generate.py`, `athena-srs generate`)
