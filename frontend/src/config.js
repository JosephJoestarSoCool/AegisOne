/**
 * Single place that decides where the API lives.
 *
 *   VITE_API_URL   public, non-secret. Production (Vercel): the deployed FastAPI origin, e.g. https://aegisone-api.vercel.app
 *                  Local development: leave unset to use the Vite dev proxy to http://localhost:8000 (same-origin),
 *                  or set it to http://localhost:8000 to call the API directly (CORS allows http://localhost:5173).
 *
 * Nothing in the bundle hardcodes a localhost URL. If VITE_API_URL is missing in a production build, requests go to
 * the frontend's own origin and the UI shows its "couldn't reach the API" state rather than inventing data.
 */
export const API_URL = String(import.meta.env.VITE_API_URL ?? '').trim().replace(/\/+$/, '')

export const apiUrl = (path, params) => API_URL + '/api' + path + (params ? '?' + new URLSearchParams(params) : '')
