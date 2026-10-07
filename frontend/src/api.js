import { useCallback, useEffect, useRef, useState } from 'react'

async function j(r) {
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`)
  return r.json()
}
export const get = (path, params) =>
  fetch('/api' + path + (params ? '?' + new URLSearchParams(params) : '')).then(j)
export const post = (path, body) =>
  fetch('/api' + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(j)

/** Fetch on mount and whenever path/params change. `reload()` refetches without clearing data. */
export function useApi(path, params) {
  const [state, set] = useState({ data: null, error: null, loading: true })
  const seq = useRef(0)
  const key = JSON.stringify(params)
  const load = useCallback(() => {
    const n = ++seq.current
    get(path, params)
      .then((data) => n === seq.current && set({ data, error: null, loading: false }))
      .catch((error) => n === seq.current && set((s) => ({ ...s, error, loading: false })))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, key])
  useEffect(() => {
    set((s) => ({ ...s, loading: true }))
    load()
  }, [load])
  return { ...state, reload: load }
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
