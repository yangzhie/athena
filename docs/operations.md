# Single-host operation

Use `bash scripts/setup.sh`, then `npm run dev:all`. The launcher starts the web
app, API, material worker and private Python worker. Each process shares absolute
paths under `ATHENA_DATA_ROOT` (default repository `data/`). Stop with Ctrl-C.
The API remains the only application API; the agent runs in process. Workers have
no public ports. Only the Python worker needs Docker access. Never expose Docker's
socket to browsers or execute generated Python in the API process.

Persistent volume layout:

- `data/athena.db`: Offerings, Environments, private sessions, materials/jobs, Practice,
  aggregates, Playground state and execution queue/results.
- `data/agent.db`: private agent snapshots and operation receipts.
- `data/materials/`: immutable upload versions and processing caches.

Override paths with `ATHENA_DB`, `ATHENA_AGENT_DB`, `ATHENA_MATERIAL_ROOT` or set
`ATHENA_DATA_ROOT` for the launcher. Configure `OPENAI_API_KEY` and `OPENAI_MODEL`
in `.env`; no file contents or credentials are logged. The API reads `.env` upward
from its working directory. No account registration or UI role switch grants authority.
Behind HTTPS set `ATHENA_SECURE_COOKIES=1` and preserve the original host. Serve web
and `/api` through the same trusted origin; localhost Vite proxy is for development.

The indexer requires ffmpeg/ffprobe and the `workers/indexer` uv environment.
`ATHENA_WHISPER_MODEL` selects the local transcription model; its first use may
download weights. Unsupported extraction fails visibly and can be retried.
`ATHENA_INDEXER_COMMAND` can select an installed external indexer command; it is
server configuration only. The worker's persisted leases/fencing prevent stale
jobs overwriting newer results.

Python defaults: 5 seconds, 256 MiB RAM, 32 processes, 16 KiB input, 64 KiB combined
output, 16 MiB temporary workspace, two concurrent jobs, 16 queued jobs. Each job
uses an unprivileged, read-only container without network, mounts or credentials.
Use `ATHENA_PYTHON_IMAGE` to pin a reviewed image digest; pre-pull it. Container
isolation is suitable for this local first version, but a public untrusted execution
service needs dedicated hosts/daemon isolation and deployment security review.
The host Docker daemon must never be reachable through an application endpoint.

Operational controls (per API process; one process for this SQLite deployment):

| Setting | Default |
| --- | --- |
| `ATHENA_MODEL_CONCURRENCY` | 4 |
| `ATHENA_MODEL_CALLS_PER_MINUTE` | 60 |
| `ATHENA_REQUESTS_PER_MINUTE` | 300 per remote peer |
| `ATHENA_DOCUMENT_MAX_BYTES` | 50 MiB |
| `ATHENA_RECORDING_MAX_BYTES` | 500 MiB |
| `ATHENA_OFFERING_STORAGE_BYTES` | 5 GiB |
| `ATHENA_TOTAL_STORAGE_BYTES` | 20 GiB |
| `ATHENA_PROCESSING_QUEUE_LIMIT` | 64 |
| `ATHENA_PRIVATE_RETENTION_DAYS` | 30 |

`GET /health` is liveness. `GET /ready` reports tutor mode, built Playground engine,
retention sweep health and worker heartbeats. It returns HTTP 503 while required components are not ready and does not make a paid model call. Health/readiness checks do not issue anonymous identities.
Model availability still depends on provider quota/account access. Requests get a
server-generated `X-Request-ID`; correlated logs use route templates and timing,
never private paths, bodies, source text or credentials. Configure trusted proxy
peer handling before exposing this to the internet; per-peer limits otherwise
apply to the proxy as a whole.

Stop all services before backing up or restoring the volume:

```sh
python3 scripts/backup.py backup data backups/athena-YYYYMMDD
python3 scripts/backup.py restore backups/athena-YYYYMMDD /path/to/new-data
ATHENA_DATA_ROOT=/path/to/new-data npm run dev:all
```

The destination must be new; SQLite backup/integrity checks run for both databases.
Keep the material directory with the databases so versioned citations remain valid.
Protect backups as private data and expire them under the same policy. Never put
runtime volumes, backups, course material, keys or autonomous workflow files in Git.

Browser tests use the explicitly separate `apps/api/tests/e2e_app.py` factory and
synthetic model/material fixtures, plus real API/storage/extraction. Docker limits
are tested separately with `ATHENA_TEST_DOCKER=1`. Default test runs are offline.
Live acceptance is optional and incurs charges:

```sh
apps/api/.venv/bin/python scripts/live-acceptance.py --allow-paid-calls --model MODEL
```

It uses synthetic material, at most twelve SDK calls with SDK retries disabled,
and writes content-free latency/token metrics to `/tmp/athena-live-acceptance.json`.
The cost estimate currently applies only to GPT-4.1 mini pricing; use actual provider
billing for other models. A small acceptance pass is not a full quality evaluation.
