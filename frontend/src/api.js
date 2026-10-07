import { useCallback, useEffect, useRef, useState } from 'react'

async function j(r) {
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`)
  return r.json()
}
export const get = (path, params) =>
  fetch('/api' + path + (params ? '?' + new URLSearchParams(params) : '')).then(j)
export const post = (path, body) =>
  fetch('/api' + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(j)

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
