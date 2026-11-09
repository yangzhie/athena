# apps/web

React + TypeScript + Vite + Tailwind v4 frontend. Runs on mock data for now.

```sh
npm run dev      # from the repo root, or from this folder
```

## Structure

- `src/app/`: router, layout and the feature registry (`features.ts`).
- `src/features/<name>/`: one folder per feature (pages, loader, `routes.tsx`, local components).
- `src/components/`: shared UI (`ui/`) and quiz components (`quiz/`).
- `src/api/`: data access. Returns mocks today; swap the bodies for `fetch()` later and keep the signatures.
- `src/types/`, `src/mocks/`, `src/lib/`: domain types, mock data, helpers.

## Adding a feature

1. Create `src/features/<name>/` with a page and a `routes.tsx` exporting a `Feature`.
2. Add one line to `src/app/features.ts`.
