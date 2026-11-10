import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './tests/browser', timeout: 120000, workers: 1,
  use: { baseURL: 'http://127.0.0.1:5173', headless: true, trace: 'retain-on-failure' },
  webServer: [
    { command: 'ATHENA_DB=/tmp/athena-browser/host.db ATHENA_MATERIAL_ROOT=/tmp/athena-browser/materials OPENAI_API_KEY= OPENAI_MODEL= apps/api/.venv/bin/python -m uvicorn e2e_app:app --app-dir apps/api/tests --port 8000 --no-access-log', url: 'http://127.0.0.1:8000/health', reuseExistingServer: false },
    { command: 'npm run dev -w @athena/web -- --host 127.0.0.1', url: 'http://127.0.0.1:5173', reuseExistingServer: false },
  ],
})
