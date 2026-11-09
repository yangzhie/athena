# packages/shared

Types shared between `apps/web` and `apps/api`. Empty for now; the frontend's
hand-written types live in `apps/web/src/types`.

Planned: TypeScript types generated from the API's OpenAPI schema
(e.g. with `openapi-typescript`), so a renamed field in Python breaks the web build
instead of failing silently at runtime. Add a `package.json` and list this
folder under `workspaces` in the root `package.json` when it gets code.
