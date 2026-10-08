import { defineConfig } from '@playwright/test'

/**
 * E2E runs an isolated stack that it starts itself: its own ports and its own database file,
 * never reusing whatever happens to be on :8000/:5173 (a stale process would silently test old code).
 * `reuseExistingServer: false` makes startup fail loudly if the ports are already taken.
 * e2e/global-setup.js then verifies the backend is the current build before any browser test runs.
 */
const API_PORT = 8101
const UI_PORT = 5183
const API = `http://127.0.0.1:${API_PORT}`
const UI = `http://127.0.0.1:${UI_PORT}`

export default defineConfig({
  testDir: './e2e',
  workers: 1,
  timeout: 60_000,
  reporter: 'list',
  globalSetup: './e2e/global-setup.js',
  use: { baseURL: UI, channel: 'chrome', trace: 'retain-on-failure' },
  webServer: [
    {
      command: `"../backend/.venv/Scripts/python.exe" -m uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port ${API_PORT}`,
      env: { AEGIS_DB: '../data/e2e.db' },
      url: `${API}/api/health`, reuseExistingServer: false, timeout: 90_000,
    },
    {
      command: 'npm run dev',
      env: { AEGIS_API_URL: API, AEGIS_UI_PORT: String(UI_PORT) },
      url: UI, reuseExistingServer: false, timeout: 60_000,
    },
  ],
})
