# Shared contracts

`api.ts` and `openapi.json` are generated from the host API. `playground.json`
exports the actual component catalogue plus JSON schemas generated from its
TypeScript Scene, Action, Check, observation, snapshot, tool and result types.
Frontend adapter signatures remain stable; session DTOs now use generated types.

From the repository root:

```sh
apps/api/.venv/bin/python scripts/generate-contracts.py
npm run contracts:check
```

Generation uses temporary databases and disables model credentials. Check in the
resulting contract changes with their implementation. Do not edit generated files.
