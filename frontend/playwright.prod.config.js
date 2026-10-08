import { defineConfig } from '@playwright/test'

/**
 * Production-style smoke test: the frontend is BUILT (not the dev server) with VITE_API_URL pointing at a
 * separate backend origin, exactly like Vercel -> hosted FastAPI. The backend starts from a missing database file
 * (cold start: DB generation + model load) and only allows the preview origin via AEGIS_CORS_ORIGINS.
 *   npm run test:prod
 */
const API = 'http://127.0.0.1:8201'
const UI = 'http://127.0.0.1:4173'

export default defineConfig({
  testDir: './e2e-prod',
  workers: 1,
  timeout: 90_000,
  reporter: 'list',
  use: { baseURL: UI, channel: 'chrome', trace: 'retain-on-failure' },
  webServer: [
    {
      command: `node -e "require('fs').rmSync('../backend/data/prod-smoke.db',{force:true})" && "../backend/.venv/Scripts/python.exe" -m uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8201`,
      env: { AEGIS_DB: '../backend/data/prod-smoke.db', AEGIS_CORS_ORIGINS: UI },
      url: `${API}/api/health`, reuseExistingServer: false, timeout: 120_000,
    },
    {
      command: 'npm run build && npm run preview -- --host 127.0.0.1 --port 4173 --strictPort',
      env: { VITE_API_URL: API },
      url: UI, reuseExistingServer: false, timeout: 120_000,
    },
  ],
})
