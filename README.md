# Athena

Adaptive learning inside university Offerings, with shared course material and
private student Environments. No registration or login is required. See [AGENTS.md](AGENTS.md)
for the product terminology and [operations](docs/operations.md) for deployment.

| Path | Implemented behavior |
| --- | --- |
| `apps/web` | API-backed study spaces, uploads/library, adaptive sessions, Practice/progress, Playground and lecturer aggregates |
| `apps/api` | SQLite host API, opaque browser identities, in-process agent, durable operations, sharing and retention |
| `agent` | Planning, assessment, grounded teaching and recoverable learning state |
| `workers/indexer` | Durable upload integration, local transcription, proposed lecture clips and lecturer approval |
| `packages/playground` | Shared TypeScript scenes, component catalogue, validation and pure transitions; standalone fixtures remain separate |
| `packages/shared` | Generated OpenAPI TypeScript and machine-readable Playground contracts |
| `scripts` | Reproducible startup, contract generation, stopped-volume backup/restore and opt-in live acceptance |

From the repository root (Node 22+, Python 3.12+, uv, ffmpeg/ffprobe, Poppler and Docker):

```sh
bash scripts/setup.sh
# Keep OPENAI_API_KEY in .env and set OPENAI_MODEL to a supported model.
npm run dev:all
```

Open http://127.0.0.1:5173. An administrator first issues a one-time lecturer invite:

```sh
apps/api/.venv/bin/python -m athena_api.spaces.cli create-lecturer-invite
```

Use the same `ATHENA_DB` as the running API (default `data/athena.db` from the root).
The lecturer enters the code under **Lecturer access** in the sidebar. Invites expire
after 24 hours and work once. Students cannot create Units/Offerings or upload material,
even by calling the API or changing their browser role preference. Existing creators
also need an explicit lecturer grant; old creator permissions alone are insufficient.

As an authorised lecturer, create a study space, upload material, publish ready
documents and the Offering, then start a learning session. Recording processing
proposes clips; approve them before students use them. The creator's browser owns
management access. Keep its cookies; identity recovery is not implemented.

`ATHENA_TUTOR=demo npm run dev:all` explicitly selects a synthetic Bubble Sort
fixture for development. Demo tutor state is in memory, and the AI Playground is
unavailable in this mode. Normal AI operation never silently falls back to fixtures.
Missing credentials/configuration return an identifiable unavailable state.

```sh
apps/api/.venv/bin/python -m pytest apps/api/tests agent/tests
workers/indexer/.venv/bin/python -m pytest workers/indexer/tests
npm test -w @athena/web
npm run lint
npm run build
npm run lint:playground
npm run contracts:check
npx playwright test
ATHENA_TEST_DOCKER=1 apps/api/.venv/bin/python -m pytest apps/api/tests/test_execution_worker.py
```

The first version targets a single host. Python runs in private, bounded Docker
containers; canvas probes remain conceptual, and tracing/variable inspection are
explicitly unsupported. Private learning content expires after 30 days by default.
Lecturer metrics require five contributing Environments and never include raw
answers or chat. Explicit sharing includes the whole saved discussion, including
Playground discussion, and is anonymous and revocable. Historical aggregate
rollups are not retained after deletion. OCR is reported unavailable for scanned
PDFs. Open-ended answers support microphone dictation with transcript review before
submission; recordings are not saved by Athena. Multi-host scaling, identity recovery
and hardened public deployment remain production work; see [operations](docs/operations.md).
For the checked demonstration flow and known limits, see [demo readiness](docs/demo-readiness.md).
