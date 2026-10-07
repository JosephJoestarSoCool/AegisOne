import { defineConfig } from '@playwright/test'

/** E2E runs against the real backend + dev server. State-mutating specs reset the demo DB first. */
export default defineConfig({
  testDir: './e2e',
  workers: 1,
  timeout: 60_000,
  reporter: 'list',
  use: { baseURL: 'http://localhost:5173', channel: 'chrome', trace: 'retain-on-failure' },
  webServer: [
    {
      command: '..\\backend\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --app-dir ..\\backend --port 8000',
      url: 'http://localhost:8000/api/health', reuseExistingServer: true, timeout: 60_000,
    },
    { command: 'npm run dev', url: 'http://localhost:5173', reuseExistingServer: true, timeout: 60_000 },
  ],
})
