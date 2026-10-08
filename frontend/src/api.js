import { useCallback, useEffect, useRef, useState } from 'react'

import { apiUrl } from './config'

export class ApiError extends Error {
  constructor(kind, status) {
    super(kind === 'network' ? 'network' : `HTTP ${status}`)
    this.kind = kind        // 'network' (could not reach the API) | 'http' (API answered with an error)
    this.status = status
  }
}

async function j(r) {
  // Never surface response bodies (they can contain server internals) to the UI.
  if (!r.ok) throw new ApiError('http', r.status)
  try { return await r.json() } catch { throw new ApiError('http', r.status) }     // e.g. an HTML page from a mis-pointed API URL
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const RETRY_DELAYS = [500, 1500]          // a cold-starting host usually answers on the 2nd or 3rd try
const inflight = new Map()                // identical concurrent GETs share one request

async function getOnce(u) {
  let res
  try { res = await fetch(u) } catch { throw new ApiError('network') }
  return j(res)
}

export function get(path, params) {
  const u = apiUrl(path, params)
  if (inflight.has(u)) return inflight.get(u)
  const run = (async () => {
    for (let i = 0; ; i++) {
      try { return await getOnce(u) } catch (e) {
        const transient = e.kind === 'network' || [502, 503, 504].includes(e.status)
        if (!transient || i >= RETRY_DELAYS.length) throw e
        await sleep(RETRY_DELAYS[i])
      }
    }
  })().finally(() => inflight.delete(u))
  inflight.set(u, run)
  return run
}

export const post = async (path, body) => {
  let res
  try {
    res = await fetch(apiUrl(path), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  } catch { throw new ApiError('network') }
  return j(res)
}

/** Any "Try again" button calls this; every mounted useApi hook refetches. */
export const retryAll = () => window.dispatchEvent(new Event('aegis:retry'))

/**
 * Fetch on mount and whenever path/params change. Data from a previous path/params is never returned
 * (so switching company can never show the previous company's data). `reload()` refetches in place.
 */
export function useApi(path, params) {
  const key = path + JSON.stringify(params)
  const [state, set] = useState({ key, data: null, error: null })
  const seq = useRef(0)
  const load = useCallback(() => {
    const n = ++seq.current
    get(path, params)
      .then((data) => n === seq.current && set({ key, data, error: null }))
      .catch((error) => n === seq.current && set((s) => ({ key, data: s.key === key ? s.data : null, error })))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  useEffect(() => { load() }, [load])
  useEffect(() => {
    const again = () => { set((s) => (s.error ? { ...s, error: null } : s)); load() }
    window.addEventListener('aegis:retry', again)
    return () => window.removeEventListener('aegis:retry', again)
  }, [load])
  const fresh = state.key === key
  return { data: fresh ? state.data : null, error: fresh ? state.error : null, loading: !fresh || (!state.data && !state.error), reload: load }
}

export const inr = (n, d = 0) =>
  (n < 0 ? '−' : '') + '₹' + Math.abs(n).toLocaleString('en-IN', { maximumFractionDigits: d })
export const compact = (n) => {
  const a = Math.abs(n)
  const s = a >= 1e7 ? (a / 1e7).toFixed(2) + ' Cr' : a >= 1e5 ? (a / 1e5).toFixed(2) + ' L' : a >= 1e3 ? (a / 1e3).toFixed(1) + 'k' : a.toFixed(0)
  return (n < 0 ? '−' : '') + '₹' + s
}
export const pct = (x, d = 0) => (x * 100).toFixed(d) + '%'
export const plus = (n, f = inr) => (n > 0 ? '+' : '') + f(n)
