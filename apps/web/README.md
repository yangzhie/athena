# apps/web

React + TypeScript + Vite + Tailwind v4 frontend. Learning sessions, lecture clips and spaced repetition use `apps/api`; unit enrolments and the Playground tutor still use mocks. Run the API on port 8000 (see `../api/README.md`); Vite proxies `/api` to it.

```sh
npm run dev      # from the repo root, or from this folder
```

```sh
npm test         # Vitest tests under src/; Node's test runner is kept separate
```

## Structure

- `src/app/`: router, layout and the feature registry (`features.ts`).
- `src/features/<name>/`: one folder per feature (pages, loader, `routes.tsx`, local components).
- `src/components/`: shared UI (`ui/`) and quiz components (`quiz/`).
- `src/api/`: data access. API-backed sessions and reviews, with mock adapters for capabilities not connected yet.
- `src/types/`, `src/mocks/`, `src/lib/`: domain types, mock data, helpers.

## Playground integration

Open a learning session, then follow its Playground link or a suggested scene. The route is
`/units/:offeringId/s/:sessionId/playground`; returning to chat keeps the same session.
Canvases and demo messages are isolated per session and retained while this tab stays open,
including across API refreshes. They are **not persisted or shared with lecturers**. The share
preview counts only saved messages. Questions and teaching activities beside the canvas still
use the real learning-session API. Older offering-only Playground URLs return to the unit's
session picker rather than choosing an arbitrary session.

## Adding a feature

1. Create `src/features/<name>/` with a page and a `routes.tsx` exporting a `Feature`.
2. Add one line to `src/app/features.ts`.
