import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { compact, inr, pct, plus, post, useApi } from '../api'
import { C, Loading, Tip, axis } from '../components'
import { shortName } from './Optimizer'

const DIMS = [['profitability', 'Profitability'], ['growth', 'Growth'], ['revenue', 'Revenue'], ['inventory', 'Inventory'], ['cac', 'CAC'], ['risk', 'Risk']]

function Slider({ label, value, min, max, step, onChange, fmt }) {
  const id = useId()
  return (
    <div className="slider">
      <label htmlFor={id}><span>{label}</span><b className="num">{fmt ? fmt(value) : value}</b></label>
      <input id={id} type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </div>
  )
}

export default function WhatIf({ company, preset }) {
  const plan = useApi('/plan', { company_id: company })
  const [budget, setBudget] = useState(0)
  const [sku, setSku] = useState('')
  const [stock, setStock] = useState(null)
  const [priceP, setPriceP] = useState(0)
  const [costP, setCostP] = useState(0)
  const [weights, setWeights] = useState(null)
  const [minRoas, setMinRoas] = useState(null)
  const [minMargin, setMinMargin] = useState(null)
  const [res, setRes] = useState(null)
  const [busy, setBusy] = useState(false)
  const seq = useRef(0)

  const skus = useMemo(() => {
    if (!plan.data) return []
    const m = new Map()
    Object.values(plan.data.campaigns).forEach((c) => m.set(c.sku_id, c))
    return [...m.values()]
  }, [plan.data])

  useEffect(() => {  // reset when company changes
    setBudget(0); setPriceP(0); setCostP(0); setSku(''); setStock(null); setWeights(null); setMinRoas(null); setMinMargin(null); setRes(null)
  }, [company])
  useEffect(() => {  // preset from the guided demo
    if (preset && skus.length) { setSku(preset.sku); setStock(preset.on_hand) }
  }, [preset, skus])
  useEffect(() => {
    if (!plan.data) return
    setWeights((w) => w || { ...plan.data.policy.weights })
    setMinRoas((v) => v ?? plan.data.policy.min_roas)
    setMinMargin((v) => v ?? plan.data.policy.min_margin)
    if (skus[0]) setSku((cur) => cur || skus[0].sku_id)
  }, [plan.data, skus])

  const cur = skus.find((s) => s.sku_id === sku)
  const scenario = useMemo(() => {
    if (!plan.data || !cur || !weights) return null
    const ov = {}
    if (stock !== null && Math.round(stock) !== Math.round(cur.on_hand)) ov.on_hand = stock
    if (priceP) ov.price = cur.price * (1 + priceP / 100)
    if (costP) ov.unit_cost = cur.unit_cost * (1 + costP / 100)
    const p = plan.data.policy
    return {
      total_budget_delta: budget,
      sku_overrides: Object.keys(ov).length ? { [sku]: ov } : {},
      weights,
      constraints: { min_roas: minRoas, min_margin: minMargin },
      _w: p.weights,
    }
  }, [plan.data, cur, weights, stock, priceP, costP, budget, sku, minRoas, minMargin])

  useEffect(() => {
    if (!scenario) return
    const n = ++seq.current
    setBusy(true)
    const { _w, ...sc } = scenario
    const t = setTimeout(() => {
      post('/whatif', { company_id: company, scenario: sc }).then((r) => { if (n === seq.current) { setRes(r); setBusy(false) } }).catch(() => setBusy(false))
    }, 160)
    return () => clearTimeout(t)
  }, [scenario, company])

  if (!plan.data || !weights || !cur) return <div className="page"><Loading error={plan.error} /></div>
  const stockVal = stock ?? cur.on_hand
  const reset = () => { setBudget(0); setPriceP(0); setCostP(0); setStock(null); setWeights({ ...plan.data.policy.weights }); setMinRoas(plan.data.policy.min_roas); setMinMargin(plan.data.policy.min_margin) }
  const setW = (k, v) => setWeights((w) => ({ ...w, [k]: v }))
  const wsum = Object.values(weights).reduce((a, b) => a + b, 0) || 1

  return (
    <div className="page">
      <div className="grid g-4-8" style={{ alignItems: 'start' }}>
        <div className="card stack" style={{ position: 'sticky', top: 80 }}>
          <div className="row between"><h3 style={{ margin: 0 }}>Change the business</h3><button className="btn ghost small" onClick={reset}>Reset</button></div>
          <Slider label="Total daily budget" value={budget} min={-40000} max={40000} step={1000} onChange={setBudget} fmt={(v) => (v > 0 ? '+' : '') + inr(v)} />
          <div className="stack" style={{ gap: 10, paddingTop: 6, borderTop: '1px solid var(--line)' }}>
            <div className="slider"><label htmlFor="whatif-sku"><span>SKU</span></label>
              <select id="whatif-sku" value={sku} onChange={(e) => { setSku(e.target.value); setStock(null); setPriceP(0); setCostP(0) }}>
                {skus.map((s) => <option key={s.sku_id} value={s.sku_id}>{s.sku_name}</option>)}
              </select></div>
            <Slider label={`Inventory on hand (now ${Math.round(cur.on_hand).toLocaleString('en-IN')})`} value={Math.round(stockVal)} min={0} max={Math.round(cur.on_hand * 1.5)} step={Math.max(1, Math.round(cur.on_hand / 100))} onChange={setStock} fmt={(v) => v.toLocaleString('en-IN') + ' units'} />
            <Slider label={`Price (now ${inr(cur.price)})`} value={priceP} min={-30} max={30} step={1} onChange={setPriceP} fmt={(v) => (v > 0 ? '+' : '') + v + '%'} />
            <Slider label={`Unit cost → margin (now ${pct(cur.margin)})`} value={costP} min={-20} max={40} step={1} onChange={setCostP} fmt={(v) => (v > 0 ? '+' : '') + v + '%'} />
          </div>
          <div className="stack" style={{ gap: 10, paddingTop: 6, borderTop: '1px solid var(--line)' }}>
            <div className="muted small" style={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em' }}>Company priorities</div>
            {DIMS.map(([k, l]) => <Slider key={k} label={l} value={Math.round(weights[k] * 100)} min={0} max={60} step={1} onChange={(v) => setW(k, v / 100)} fmt={(v) => pct(v / 100 / wsum)} />)}
          </div>
          <div className="stack" style={{ gap: 10, paddingTop: 6, borderTop: '1px solid var(--line)' }}>
            <div className="muted small" style={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em' }}>Guardrails</div>
            <Slider label="Minimum ROAS" value={minRoas} min={1} max={10} step={0.5} onChange={setMinRoas} fmt={(v) => v.toFixed(1) + '×'} />
            <Slider label="Minimum margin" value={minMargin} min={0.05} max={0.7} step={0.01} onChange={setMinMargin} fmt={(v) => pct(v)} />
          </div>
        </div>

        <div className="stack" style={{ opacity: busy ? 0.7 : 1, transition: 'opacity 150ms var(--ease-out)' }}>
          {!res ? <div className="loading">Solving…</div> : <Result res={res} />}
        </div>
      </div>
    </div>
  )
}

function TopCard({ title, tone, r }) {
  return (
    <div className="card" style={tone === 'new' ? { borderColor: 'var(--gold)' } : undefined}>
      <h3>{title}</h3>
      {r ? (<div className="stack" style={{ gap: 8 }}>
        <div style={{ fontWeight: 650, fontSize: 15 }}>{r.title}</div>
        <div className="row"><b className="up num" style={{ fontSize: 20 }}>{plus(r.expected_profit)}/day</b><span className="muted small">confidence {pct(r.confidence)}</span></div>
      </div>) : <div className="muted">No budget move clears the guardrails.</div>}
    </div>
  )
}

function Result({ res }) {
  const chart = res.allocation_diff.map((a) => ({ name: shortName(a.name), Baseline: a.baseline, Scenario: a.scenario }))
  const t = res.scenario.totals
  return (
    <>
      <div className={'banner ' + (res.changed ? 'changed' : '')}>
        <div className="row" style={{ marginBottom: 6 }}><span className={'pill ' + (res.changed ? 'gold' : '')}>{res.changed ? 'Recommendation changed' : 'Recommendation unchanged'}</span></div>
        {res.narrative}
      </div>
      <div className="grid g2">
        <TopCard title="Baseline top move" r={res.top_before} />
        <TopCard title="Scenario top move" r={res.top_after} tone={res.changed ? 'new' : ''} />
      </div>
      <div className="grid g3">
        <div className="card kpi"><div className="label">Scenario profit gain</div><div className="value up num">{plus(t.incremental_profit)}</div><div className="muted small">per day · {compact(t.incremental_profit_30d)} / 30d</div></div>
        <div className="card kpi"><div className="label">vs baseline</div><div className={'value num ' + (res.profit_delta >= 0 ? 'up' : 'down')}>{plus(res.profit_delta)}</div><div className="muted small">per day</div></div>
        <div className="card kpi"><div className="label">Total budget</div><div className="value num">{inr(t.budget_after)}</div><div className="muted small">{t.budget_after === t.budget_before ? 'unchanged' : plus(t.budget_after - t.budget_before) + ' vs today'}</div></div>
      </div>
      <div className="card">
        <h3>Allocation · baseline plan vs scenario plan</h3>
        <ResponsiveContainer width="100%" height={Math.max(300, chart.length * 32)}>
          <BarChart data={chart} layout="vertical" margin={{ left: 16, right: 16 }} barCategoryGap={6}>
            <CartesianGrid stroke={C.line} horizontal={false} />
            <XAxis type="number" {...axis} tickFormatter={compact} />
            <YAxis type="category" dataKey="name" {...axis} width={170} />
            <Tooltip content={<Tip fmt={(v) => inr(v)} />} cursor={{ fill: 'rgba(255,255,255,.04)' }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="Baseline" fill="#3a4a6d" radius={3} isAnimationActive={false} />
            <Bar dataKey="Scenario" fill={C.gold} radius={3} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="card">
        <h3>Scenario recommendations</h3>
        <table className="table"><tbody>
          {res.scenario.recommendations.slice(0, 6).map((r) => (
            <tr key={r.rec_id}><td>{r.title}</td><td className="r up num">{plus(r.expected_profit)}/day</td><td className="r muted num">{pct(r.confidence)}</td></tr>
          ))}
          {!res.scenario.recommendations.length && <tr><td className="muted">None.</td></tr>}
        </tbody></table>
      </div>
    </>
  )
}
