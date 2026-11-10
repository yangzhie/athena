# apps/api

Athena's FastAPI modular monolith serves private learning sessions, the in-process
adaptive tutor, Practice (SRS), approved lecture clips and anonymous session sharing.

## Setup and test

Run from `apps/api/`:

```sh
uv sync
uv run pytest
```

The API tests use real in-process ASGI requests with a test-only polling selector
(`tests/http_client.py`). Its event loop checks queued callbacks at least every
10 ms, including in sandboxes where cross-thread socket wakeups are unavailable.
Routes, authentication dependencies, worker threads and storage run normally;
no permissions or network server are required. To verify answer replay, restart
recovery, failed-write reconciliation and ownership with explicitly selected
offline model fixtures, run `uv run pytest tests/test_answer_retries.py`.

## Run

```sh
uv run athena-srs load-starter    # once: CSE5ALG and CSE5DMI starter banks
ATHENA_TUTOR=demo ATHENA_DEV_STUDENT_ID=dev-student ATHENA_DEV_LECTURER_ID=dev-lecturer uv run uvicorn athena_api.app:create_app --factory --reload
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
| *(unset)* or `ai` | the agent with configured `OPENAI_API_KEY` and `OPENAI_MODEL`; missing configuration returns 503 |
| `placeholder` | explicitly selected, labelled canned text replies; no questions |
| `demo` | explicitly selected, labelled synthetic Bubble Sort fixture; in-memory agent state is lost on restart |

Unknown modes return an unavailable tutor. `GET /tutor/status` identifies `mode`,
`available` (configuration/storage readiness, without a provider probe), and
`scripted`. Provider/model/storage failures return an error; they never switch to
canned replies. No model call is made to check status. The setup command above
explicitly selects offline fixtures. AI operation uses the existing upward `.env`
loader and preserves process configuration. Credentials alone do not authorize
paid verification: live acceptance remains blocked until explicit opt-in (H5).

Agent memory lives in its own database, `ATHENA_AGENT_DB` (default `data/agent.db`).

**Answer retries.** The question ID identifies one accepted answer within a
student's session. Identical retries return the original stored learner and tutor
messages (including IDs and timestamps), even after later turns or a restart.
Changing the choice, trimmed answer text, or `hint_used` returns 409; `shown` is
only a display label and cannot rewrite an accepted answer. The host saves the
exchange, session timestamp and private retry receipt atomically. If that write
fails after the agent accepts the answer, retry the same submission: the agent
replays its transition and the host saves the missing exchange. Concurrent host
writes keep the first committed exchange. The web chat merges stored message IDs
so a replay doesn't duplicate the visible answer.

Retry receipts are private, scoped to the owning student and session, excluded
from lecturer projections, and deleted with the host session. Existing databases
gain the receipt table automatically. Answers saved before receipt support cannot
be safely compared because their submitted choice/hint metadata was not retained;
resubmitting those questions returns 409 with a refresh instruction.

**Coordinated operations and recovery.** Creation and chat accept an optional
`Idempotency-Key` header (1–128 letters, digits, underscores or hyphens). The web
adapter always supplies one; other clients must retain it to retry after an
uncertain response. The same key and normalized payload replay the exact stored
result. Reusing a key with different input returns 409. Without a key, creation
and chat are intentionally new operations; two new sessions with the same goal
have separate conversations. Answers use their question ID; continuation uses its
teaching activity ID and always replays its accepted result.

The private host journal reserves the operation before invoking the tutor. The
agent stages its transition and commits its result receipt with the same atomic
snapshot/revision comparison. The host then publishes the entire exchange,
updated timestamp, answer receipt where applicable, and completion outcome in one
transaction. An interrupted host write leaves the old conversation intact and the
operation pending. Retrying after reopening both databases uses the accepted agent
receipt without another model call or duplicate assessment evidence. Independent
adapters converge on the winning stored transition. Concurrent different operations
in one session return 409 until the pending operation is recovered. Invalid input
that the tutor rejected before publication can be corrected; transient failures
remain pending for retry. Storage failures return a safe 503, never database details.

`POST /units/{offering}/sessions/operations/{operation_id}/retry` recovers using the
server's saved input and returns `{session, messages}`. Operation IDs are
`start:<key>`, `message:<key>`, `answer:<question_id>` or `continue:<activity_id>`.
Lookup requires the authenticated owner and offering; identifiers confer no access.
The browser retains only the random key and a request digest in tab storage, not
submitted text. Refreshing the session retries its pending chat operation; refreshing
the session list recovers pending creation. When storage is disabled, retry identity
lasts only for the current page. A changed submission after an uncertain response
asks the student to refresh first. Pending operations never appear as completed
exchanges or half-created sessions.

Host journal records are removed with the host session. Agent operation receipts
remain backend-only and are excluded from conversation/learning exports and shared
session projections. The agent database automatically adds a separate private
receipt column to existing records. Complete cross-service deletion/expiry remains
the later lifecycle batch; this batch does not claim to remove existing agent memory
when a host session is deleted. Scripted demo agent state is deliberately ephemeral
and cannot resume a lost in-memory transition after a restart.

**Unit material.** When a session starts, the unit's **approved** lecture clips are
ranked against the student's goal (BM25 keywords; title and summary weigh 3× the
transcript; `sessions/material.py`) and the top 5 go to the agent as materials. It
grounds its teaching in them and cites clips (agent `VideoReference`), which the web
app opens in the side panel. If the agent finds the clips don't cover the goal, the
session starts without material and the agent labels its answers as general knowledge.

**Context budget.** The agent's default budget (16 KiB, counted in bytes) is too
small once transcripts are attached; `apps/api` gives it 128 KiB (about 32k tokens).
Override with `ATHENA_AGENT_CONTEXT_BYTES`.

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
