import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Ports/targets are overridable so E2E can run an isolated stack (see playwright.config.js).
const api = process.env.AEGIS_API_URL || 'http://127.0.0.1:8000'
const port = Number(process.env.AEGIS_UI_PORT || 5173)

export default defineConfig({
  plugins: [react()],
  server: { port, host: process.env.AEGIS_UI_PORT ? '127.0.0.1' : undefined, strictPort: !!process.env.AEGIS_UI_PORT, proxy: { '/api': api } },
})
