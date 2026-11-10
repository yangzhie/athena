# First-version verification (10 November 2026)

The direct implementation is delivered in complete feature commits. No autonomous
launcher/reviewer is required. The implementation plan and local workflow records
are intentionally excluded from Git.

Verification uses synthetic material and isolated databases. The broad checks pass: 693 API/agent tests (six opt-in Docker cases skipped),
56 indexer tests, 46 frontend tests, seven real Docker checks, the expanded browser
journey, production build, TypeScript checks and lint. The four-process launcher
also returned ready with the API, engine, retention sweep and both workers healthy. Real Docker
checks cover reproducible Python, five-second timeout, output caps, unprivileged
UID, read-only root, no application mounts/credentials, blocked networking and
container cleanup. Browser acceptance covers creation/publication, separate
identities, learning questions/continuation/retries, private persistence, source
opening, Practice recovery, Playground, execution, sharing/revocation and deletion.
Focused API tests additionally cover restart recovery, proposals/rejection,
versioned citations, clip approval and five-Environment aggregate suppression.

Session-start recovery now offers **Recover previous session** when an earlier
request has an uncertain result, instead of requiring refresh before a changed
goal. Recovery opens the original session; a confirmed missing operation unlocks
a fresh submission. Tutor/network failures retain the retry identity and show the
underlying error. Background refresh and the recovery button share one in-flight
retry. Frontend regression coverage includes these cases without paid model calls.
The browser journey also passed with a deliberately lost successful start
response: editing the goal and recovering opened exactly one original session.

Grounded session-start repair (11 November): source quotations now enter model
context through a numeric reference catalog, rather than provider schema literals.
Regression cases cover multiline/control-character/Unicode/code/long text, exact
document and transcript citations, invalid references and source conflicts. API
tests start complete grounded sessions and replay them without additional model
calls. Existing extraction, upload and context limits still apply.

A separate authorised diagnostic allowance reproduced the original HTTP 400
`invalid_json_schema` rejection and confirmed that OpenAI accepts the repaired
schema against the same material. Subsequent live verification flagged source
instruction following; the verification prompt now explicitly distinguishes
ordinary course directions from rule overrides. The allowance was exhausted before
that prompt refinement could be checked live. Full live grounded session startup
is still unverified; offline fixture success does not establish live model quality.

Material coverage and general-knowledge answers (11 November): the host now
retrieves against the current question before falling back to goal/Concept context.
Comparison ranking rewards coverage of both subjects. A read-only check of the
uploaded Data Mining slides selected pages 28, 29, 30 and 3 for the regression versus
classification question; it made no model calls and did not modify the Offering.
Topic changes retain the material selected for the current question, and ordinary
chat replies preserve citations and knowledge origin through host storage.

Chat can combine verified material-supported parts with server-labelled general
additions. Missing coverage permits a general explanation after at most one
grounded repair; teaching and hints have the same bounded fallback policy.
Assessment evaluation, source conflicts, contradictions, invalid references,
provider failures and source-instruction overrides never use that fallback.
The general-answer badge describes an inability to verify against retrieved
material rather than absence from the entire Offering. Regression tests cover
the comparison, missing/partial coverage, retry replay, database reload, anonymous
sharing, unchanged grading state and frontend provenance rendering. Verification
of this change is offline; no additional paid calls were authorised or made.
The completed checks passed: 739 agent/API tests (six opt-in skips), 57 frontend
tests, frontend lint and the production build. Final targeted checks also verified
that clarification questions do not receive a misleading general-answer badge.

A bounded paid acceptance used 12 calls total with `gpt-4.1-mini` and SDK retries
disabled. Mean model-call latency was about 2.54 seconds; token-based cost estimate
was USD 0.005435 using the [published pricing](https://developers.openai.com/api/docs/models/gpt-4.1-mini).
Two initial attempts exposed failures in unconstrained planning output. Schema
constraints now limit objectives to existing Concept IDs and evidence to exact
supplied quotes/indexes; regression tests cover both boundaries. The final five
calls completed live general-knowledge planning, an initial question, deterministic
multiple-choice assessment and a follow-up question; answer retry replay passed.

The paid budget is exhausted. Grounded full-session generation, open-ended model
grading, AI scene generation and execution-aware model interpretation were exercised
with deterministic model fixtures, but the complete live-model acceptance of these
paths remains unverified. Do not describe this bounded pass as a production-quality
model evaluation. The model used for acceptance is marked deprecated in current
OpenAI documentation; configure a supported model for ongoing deployment.

Recording integration has extraction/job/approval/media contract coverage and the
indexer has its own deterministic suite. A complete live recording transcription
and model segmentation pass has not been run as part of this release verification.
Scanned PDFs fail explicitly with an OCR-unavailable message.

Single-host SQLite/local storage, per-process quotas, cookie-loss recovery,
HTTPS/proxy hardening, dedicated execution hosts, backup retention, model-quality
assessment and larger browser/load coverage remain deployment concerns. No claim
of public-production readiness is made.
