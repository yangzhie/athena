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
ATHENA_TUTOR=demo uv run uvicorn athena_api.app:create_app --factory --reload
```

Live rephrasing turns on when `OPENAI_API_KEY` and `OPENAI_MODEL` are set (the
repo's `.env` is read automatically; `ATHENA_REPHRASE_MODEL` overrides the model).
Without them, items fall back to existing wordings and never repeat one the
student got wrong.

Data goes to `data/athena.db` (gitignored; override with `ATHENA_DB`). Interactive
docs at http://127.0.0.1:8000/docs. Normal operation uses an opaque HTTP-only,
SameSite browser cookie, with the bearer secret stored only as a hash on the server.
Cookies are Secure on HTTPS; set `ATHENA_SECURE_COOKIES=1` behind a trusted HTTPS proxy.
No registration or login is required. Keep the creator browser’s cookies: there is
no identity recovery or capability transfer in this first version.

`GET /offerings` discovers published Offerings and the caller’s own drafts.
`POST /offerings` accepts `{code,title,year,semester}` and creates a private draft
and a server-owned management grant for that browser. `POST /offerings/{id}/publish`
makes it discoverable; `DELETE /offerings/{id}` makes it unavailable. Unknown and
unpublished Offerings return 404; deleted Offerings return 410. A published Offering
has exactly one Environment per browser identity, shared by that learner’s sessions.
The UI role switch and client-supplied identity headers grant no authority.

`create_app(resolve_student=..., resolve_lecturer=...)` remains an explicit trusted
host/testing seam. Only such injected adapters can opt into the old development
resolvers. The normal application ignores `ATHENA_DEV_STUDENT_ID` and
`ATHENA_DEV_LECTURER_ID`; do not use these variables for deployed authorisation.

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

Creator-management only (403 otherwise), using the server-side grant for this Offering. No student data is returned.

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

**Unit material.** In the normal anonymous application, one Offering-scoped
provider ranks ready published document passages and approved lecture clips using
BM25 title/body matching. It selects up to five results and bounds long transcript
excerpts. New published versions replace older versions in retrieval, while old
immutable passages remain available to saved citations. Every subsequent tutor
operation refreshes selection using the current goal, Concept title and discussion.
Accepted operation retries replay the original response and references.

If initial material has insufficient coverage, the agent may start with explicitly
labelled general knowledge. Conflicting sources always return an actionable 409;
they are never discarded through that fallback. Model grounding checks verify exact
source quotes. Private question criteria remain internal. The source panel resolves
cited passages through `GET /units/{offering}/materials/{version}/passages/{id}`;
original files are downloaded only through authorised endpoints. The web material
library and lecture list do not silently select fixture data when the API is empty
or unavailable. Explicitly injected host adapters can still use `LectureMaterial`.

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

## Material upload and processing

Creators upload material from the study-space management screen. PDF, UTF-8 text,
DOCX and PPTX documents preserve their real page, slide or paragraph locations.
DOCX pages are not invented. A PDF without extractable text reports that OCR is
required. Recordings are indexed through the existing lecture pipeline; its clips
start pending and must be approved by the creator before students see them.

Run both the API and worker from `apps/api/`, sharing `ATHENA_DB` and
`ATHENA_MATERIAL_ROOT` (defaults: `data/athena.db` and `data/materials`):

```sh
# Once from the repository root; installs the separate transcription dependencies:
uv sync --project workers/indexer
# From apps/api, beside the running API:
uv run python -m athena_api.materials.worker
# Or process one pending job and exit:
uv run python -m athena_api.materials.worker --once
```

Install FFmpeg/ffprobe and Poppler/pdftotext on the host. The default recording
command invokes `uv run --project <repository>/workers/indexer index-lecture`;
`ATHENA_INDEXER_COMMAND` can select an already installed indexer. Whisper runs
locally and downloads its model on first use (`ATHENA_WHISPER_MODEL`, default
`small`); segmentation uses the configured OpenAI model. No transcription or
model call happens inside an upload request. Recordings are limited to four
hours; processing defaults to a one-hour timeout (`ATHENA_PROCESSING_TIMEOUT`).
FFmpeg input protocols are restricted to local files/pipes.

Uploads use raw bytes: `POST /units/{offering}/materials?filename=...` returns 202.
Add `replace=<material-id>` to create an immutable new version; earlier passages
remain attributable. Defaults are 50 MiB per document and 500 MiB per recording,
overridable by `ATHENA_DOCUMENT_MAX_BYTES` / `ATHENA_RECORDING_MAX_BYTES`.
`GET .../materials` shows processing states; creators can `POST .../{id}/retry`
after a failure and `POST .../{id}/publish` once a document is ready. Students
can access only ready, published documents and approved lecture clips. Source
files and extracted passages use authorised endpoints, never public static paths.

The durable SQLite queue uses worker leases and fencing tokens. Restarted workers
reclaim expired jobs; stale workers cannot publish a later worker’s result.
Recording transcription keeps its existing per-chunk cache for retries. Failed
jobs remain visible with a safe explanation; retry is explicit. Keep database,
material storage and indexing caches on persistent storage and out of Git.

## Learner profile, Practice and class aggregates

`GET /learner/profile` returns only the caller’s cross-unit Concept record.
`GET /units/{offering}/progress` and `/progress/evidence` project that caller’s
Concept status, concise notes and traceable assessment references. Fresh sessions
have fresh conversations; prior Concept knowledge can inform diagnosis but cannot
replace independent assessment. Unknown/developing/mastered states come from the
agent’s evidence-based mastery rules, never from a scheduled review or canvas click.
Scripted demo/placeholder output does not create learning evidence or analytics.

A small explicit canonical Concept catalogue supports safe cross-unit identity.
Unknown Concepts stay scoped to the Offering and meaning; arbitrary generated
Concept IDs are not aggregated together. Creators can define `/units/{offering}/topics`
and map them to `/concepts/catalogue` or an explicit course Concept. Those Topics
also guide subsequent recording indexing. Private generated titles never become
lecturer-facing labels; analytics use an “Other course concepts” category instead.

Tutor assessment evidence creates private Practice items per learner/Offering/Concept.
These and their live rewordings never enter the lecturer’s public bank. Practice
uses the existing FSRS scheduler; only the owning learner can answer or inspect its
feedback. `Idempotency-Key` on attempts and ratings stores the original result
atomically with the attempt/card/log. Identical retries replay it; conflicting input
returns 409. A failed transaction publishes no partial grade or schedule. Saved
unrated feedback is restored after refresh. Recovery endpoints return committed
results without asking the browser to retain private answer text.

`GET /units/{offering}/insights` requires this Offering’s creator grant. It reads
only offering-local events: canonical Concept, outcome, fixed gap category and
internal contribution references. It never reads chat text, learner answers,
private Practice questions or profile notes. Metrics require at least five distinct
Environments, with the same suppression per Concept/category. Counts describe
anonymous Environments and sessions, not verified individual students. Insufficient
real data yields an explicit empty state, without silently mixing in sample data.
