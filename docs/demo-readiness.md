# Demonstration guide — 11 November 2026

The updated app was left running at http://127.0.0.1:5173 after readiness checks.
If it has stopped, start all services from the repository root with `npm run dev:all`, then open the
web URL printed in the terminal (normally http://127.0.0.1:5173). The root `.env`
must contain `OPENAI_API_KEY`, `OPENAI_MODEL` and `ATHENA_TUTOR=ai`. Voice typing
uses `ATHENA_TRANSCRIPTION_MODEL=gpt-transcribe` by default and the same server-side
key. No key is sent to the browser.

## Suggested demonstration

1. Select Student view and a published Offering. Start a **new** session with
   “What is the difference between regression and classification?” Existing
   questions and private rubrics are preserved; new sessions use the refined policy.
2. Answer the diagnostic question. Questions should test a distinction or a
   misconception, rather than ask the student to repeat a noun in the prompt.
   Immediate feedback explains the result before the next task.
3. Open a cited source. Multiple quotations from one passage now share one chip;
   the original quotation evidence remains stored for traceability.
4. For an open-ended question, click **Speak answer**, allow microphone access,
   speak, then **Stop recording**. Review or edit the transcript and click **Answer**.
   Recording never submits an answer automatically. Permission errors and cancelled
   recordings preserve typed text. Recording is limited to 60 seconds and 2 MiB.
   Leaving the tab cancels an active recording without sending it.
   Athena does not store the recording; only a subsequently submitted text answer
   enters the private session. Transcription uses the configured external provider.
5. Ask an aside beyond the notes, starting with “As a related example…”. The answer
   should carry a general-knowledge label and preserve the current learning goal.
   Plain follow-ups such as “Why?” can still use the current goal for retrieval.
6. Refresh to demonstrate persistence. Sharing remains private by default and can
   be previewed, explicitly enabled and immediately revoked.

Lecturer operations require a server-issued grant. For a fresh browser, an
administrator can run `apps/api/.venv/bin/python -m athena_api.spaces.cli create-lecturer-invite`
against the same `ATHENA_DB`, then redeem the one-use code
under **Lecturer access**. A role switch alone never grants management permission.

## Verification and practical limits

Live browser acceptance used newly authored synthetic notes and synthetic spoken
audio, with a persistent hard limit of 50 provider requests. It used 46 requests
(45 text generation requests and one audio transcription). No further paid tests
were run. The pass verified grounded question creation, plausible distractors,
a reasoning follow-up, real transcription,
written assessment, incorrect-answer teaching, source opening, refresh and labelled
answers beyond the notes. The focused-comparison planner was checked live to return
one integrated Concept. A related out-of-material aside used two requests after the
pacing fix. No real student's session was changed by these tests.

The live pass found and fixed exact-evidence failures in grading. One bounded
repair now selects numeric references to the student's original answer; fabricated
references still fail and cannot establish mastery. It also found and fixed
repetitive comparison roadmaps, duplicate source chips, missing assessment feedback,
answer-draft carry-over and controls obscured by the composer.

Actual uploaded course slides were checked locally for extraction and retrieval.
Automatic approval review blocked exporting copied course slides for live testing,
so those paid tests were replaced with synthetic material. This pass does not
establish live answer quality for every real document. A physical microphone in
the demonstration room, noise and accents have not been tested; typed input remains
available. Use localhost or HTTPS for microphone access. Provider latency and
availability remain external dependencies.

The Playground and isolated Python execution pass the deterministic browser journey
and backend checks. New live AI scene composition was not repeated in this pass.
The application is prepared for a local demonstration, not certified for public
production deployment.

Final checks passed: 761 agent/API tests with six opt-in skips, 58 frontend tests,
frontend lint and production build, generated API contracts, and the browser journey
including microphone denial/cancellation, transcript review and visible answer controls.
The normal application's readiness endpoint reported AI mode, the Playground engine,
retention sweep, indexing worker and execution worker healthy; the web returned HTTP 200.
