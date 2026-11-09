# Athena

AI-powered adaptive learning. See [AGENTS.md](AGENTS.md) for the product vision.

## Layout

| Path | What | Status |
| --- | --- | --- |
| `apps/web` | React + TypeScript + Vite + Tailwind frontend | Static pages on mock data |
| `apps/api` | FastAPI backend (Python) | Not started |
| `workers` | Background jobs: ingestion, lecture pipeline | Not started |
| `packages/shared` | Types shared between web and api | Not started |
| `infra` | Docker Compose for Postgres, Redis, MinIO | Not started |
| `docs` | Design doc and decision records | Not started |

## Run the frontend

```sh
npm install      # from the repo root; installs all JS workspaces
npm run dev      # starts apps/web
```

`npm run build` and `npm run lint` also work from the root.
