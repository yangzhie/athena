# packages/playground

The Playground Canvas, used by `apps/web` (the unit's Playground view) and
`apps/playground` (the standalone demo).

- `src/contracts.ts`: scenes, objects, actions, checks, events and agent tools.
- `src/core/`: the canvas (store, layout, ports and wiring, checks, demonstrations), scene validation and the component catalog.
- `src/objects/`: preset object types. Each declares its config schema, ports, actions and what checks can test (`about`), which is what the model reads.
- `src/tutor/runner.ts`: the tutor's side of a scene. It plays back the responses written into the scene and hands everything else to a model hook.
- `src/fixtures/`: test scenes and mock model doubles, until a model generates scenes.

Hosts import `@athena/playground` (and `@athena/playground/fixtures` for mocks),
and add `@import "@athena/playground/styles.css";` after Tailwind.
