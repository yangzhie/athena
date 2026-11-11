import { tmpdir } from 'node:os'
import { dirname } from 'node:path'
import { defineConfig } from '@playwright/test'

const apiPort = process.env.ATHENA_E2E_API_PORT ?? '18000'
const webPort = process.env.ATHENA_E2E_WEB_PORT ?? '15173'
const database = process.env.ATHENA_E2E_DB ?? `${tmpdir()}/athena-browser-${process.pid}/host.db`
process.env.ATHENA_E2E_DB = database
export default defineConfig({
  testDir: './tests/browser', timeout: 120000, workers: 1,
  use: { baseURL: `http://127.0.0.1:${webPort}`, headless: true, trace: 'retain-on-failure' },
  webServer: [
    { command: `apps/api/.venv/bin/python -m uvicorn e2e_app:app --app-dir apps/api/tests --port ${apiPort} --no-access-log`, env: { ATHENA_DB: database, ATHENA_MATERIAL_ROOT: `${dirname(database)}/materials`, OPENAI_API_KEY: '', OPENAI_MODEL: '' }, url: `http://127.0.0.1:${apiPort}/health`, reuseExistingServer: false },
    { command: `npm run dev -w @athena/web -- --host 127.0.0.1 --port ${webPort} --strictPort`, env: { ATHENA_API_URL: `http://127.0.0.1:${apiPort}` }, url: `http://127.0.0.1:${webPort}`, reuseExistingServer: false },
  ],
})
