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
