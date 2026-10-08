import { useEffect, useId, useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { compact, inr, pct, plus, post, useApi } from '../api'
import Icon from '../icons'
import { WinnerCard } from '../decision'
import { Disclosure } from '../ui'
import { Loading, Tip } from '../components'
import { C, axis, fx, nameOf, shortName, errorText } from '../lib'

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
  if (!plan.data) return <div className="page"><Loading error={plan.error} /></div>
  return <Simulator plan={plan.data} company={company} preset={preset} />
}

function Simulator({ plan, company, preset }) {
  const pol = plan.policy
  const skus = useMemo(() => {
    const m = new Map()
    Object.values(plan.campaigns).forEach((c) => m.set(c.sku_id, c))
    return [...m.values()]
  }, [plan])
  const [budget, setBudget] = useState(0)
  const [sku, setSku] = useState(skus.some((s) => s.sku_id === preset?.sku) ? preset.sku : (plan.next_rupee?.sku_id ?? skus[0].sku_id))
  const [stock, setStock] = useState(skus.some((s) => s.sku_id === preset?.sku) ? preset.on_hand : null)
  const [priceP, setPriceP] = useState(0)
  const [costP, setCostP] = useState(0)
  const [weights, setWeights] = useState({ ...pol.weights })
  const [minRoas, setMinRoas] = useState(pol.min_roas)
  const [minMargin, setMinMargin] = useState(pol.min_margin)
  const [maxCac, setMaxCac] = useState(pol.max_cac)
  const [out, setOut] = useState(null)   // { key, data?, error? } for the scenario it answers

  const cur = skus.find((s) => s.sku_id === sku) ?? skus[0]
  const scenario = useMemo(() => {
    const ov = {}
    if (stock !== null && Math.round(stock) !== Math.round(cur.on_hand)) ov.on_hand = stock
    if (priceP) ov.price = cur.price * (1 + priceP / 100)
    if (costP) ov.unit_cost = cur.unit_cost * (1 + costP / 100)
    return {
      total_budget_delta: budget,
      sku_overrides: Object.keys(ov).length ? { [cur.sku_id]: ov } : {},
      weights,
      constraints: { min_roas: minRoas, min_margin: minMargin, max_cac: maxCac },
    }
  }, [cur, stock, priceP, costP, budget, weights, minRoas, minMargin, maxCac])
  const key = JSON.stringify(scenario)

  useEffect(() => {
    let dead = false
    const t = setTimeout(() => {
      post('/whatif', { company_id: company, scenario: JSON.parse(key) })
        .then((data) => !dead && setOut({ key, data }))
        .catch((error) => !dead && setOut({ key, error }))
    }, 160)
    return () => { dead = true; clearTimeout(t) }
  }, [key, company])

  const busy = !out || out.key !== key
  const stockVal = stock ?? cur.on_hand
  const reset = () => {
    setBudget(0); setPriceP(0); setCostP(0); setStock(null); setWeights({ ...pol.weights })
    setMinRoas(pol.min_roas); setMinMargin(pol.min_margin); setMaxCac(pol.max_cac)
  }
  const setW = (k, v) => setWeights((w) => ({ ...w, [k]: v }))
  const wsum = Object.values(weights).reduce((a, b) => a + b, 0) || 1

  return (
    <div className="page">
      <div className="grid g-4-8" style={{ alignItems: 'start' }}>
        <div className="card stack controls">
          <div className="row between"><h3 style={{ margin: 0 }}>Change the business</h3><button className="btn ghost small" onClick={reset}>Reset</button></div>
          <Slider label="Total daily budget" value={budget} min={-40000} max={40000} step={1000} onChange={setBudget} fmt={(v) => (v > 0 ? '+' : '') + inr(v)} />
          <div className="stack ctl-group">
            <div className="slider"><label htmlFor="whatif-sku"><span>Product</span></label>
              <select id="whatif-sku" value={cur.sku_id} onChange={(e) => { setSku(e.target.value); setStock(null); setPriceP(0); setCostP(0) }}>
                {skus.map((s) => <option key={s.sku_id} value={s.sku_id}>{s.sku_name}</option>)}
              </select></div>
            <Slider label={`Inventory (now ${Math.round(cur.on_hand).toLocaleString('en-IN')})`} value={Math.round(stockVal)} min={0} max={Math.round(cur.on_hand * 1.5)} step={Math.max(1, Math.round(cur.on_hand / 100))} onChange={setStock} fmt={(v) => v.toLocaleString('en-IN') + ' units'} />
            <Slider label={`Price (now ${inr(cur.price)})`} value={priceP} min={-30} max={30} step={1} onChange={setPriceP} fmt={(v) => (v > 0 ? '+' : '') + v + '%'} />
            <Slider label={`Unit cost → margin (now ${pct(cur.margin)})`} value={costP} min={-20} max={40} step={1} onChange={setCostP} fmt={(v) => (v > 0 ? '+' : '') + v + '%'} />
          </div>
          <Disclosure title="Company priorities" summary="objective weights">
            <div className="stack" style={{ gap: 10 }}>
              {DIMS.map(([k, l]) => <Slider key={k} label={l} value={Math.round(weights[k] * 100)} min={0} max={60} step={1} onChange={(v) => setW(k, v / 100)} fmt={(v) => pct(v / 100 / wsum)} />)}
            </div>
          </Disclosure>
          <Disclosure title="Guardrails" summary="ROAS, margin, CAC">
            <div className="stack" style={{ gap: 10 }}>
              <Slider label="Minimum ROAS" value={minRoas} min={1} max={10} step={0.5} onChange={setMinRoas} fmt={(v) => v.toFixed(1) + '×'} />
              <Slider label="Minimum margin" value={minMargin} min={0.05} max={0.7} step={0.01} onChange={setMinMargin} fmt={(v) => pct(v)} />
              <Slider label="Maximum CAC" value={maxCac} min={Math.round(pol.max_cac * 0.3)} max={Math.round(pol.max_cac * 2)} step={Math.max(1, Math.round(pol.max_cac / 50))} onChange={setMaxCac} fmt={(v) => inr(v)} />
            </div>
          </Disclosure>
        </div>

        <div className="stack results" aria-live="polite" aria-busy={busy}>
          <div className={'solving' + (busy ? ' on' : '')} role="status">{busy ? <span className="sr-only">Re-solving the decision</span> : null}<i /></div>
          {out?.error && <div className="err" role="alert">{errorText(out.error, 'this scenario')}</div>}
          {!out && <Loading />}
          {out?.data && <div className={'stack fade' + (busy ? ' stale' : '')}><Result res={out.data} /></div>}
        </div>
      </div>
    </div>
  )
}

function Result({ res }) {
  const nr = res.next_rupee
  const chart = res.allocation_diff.map((a) => ({ name: shortName(a.name), Baseline: a.baseline, Scenario: a.scenario }))
  const t = res.scenario.totals
  const sameCampaign = nr.before && nr.after && !nr.changed
  const dp = nr.before && nr.after ? nr.after.profit_per_rupee - nr.before.profit_per_rupee : 0
  return (
    <>
      <section className="cmp" aria-label="Next ₹1 before and after">
        <WinnerCard label="Baseline" w={nr.before} />
        <Icon name="arrow" size={22} className="cmp-arrow" />
        <div key={nr.after?.campaign_id} className="rise-in"><WinnerCard label="Simulated" w={nr.after} tone={nr.changed ? 'changed' : ''} other={nr.before} /></div>
      </section>
      <div className={'banner ' + (nr.changed ? 'changed' : '')}>
        <div className="row" style={{ marginBottom: 6 }}>
          <span className={'pill ' + (nr.changed ? 'gold' : '')}>{nr.changed ? 'Winner changed' : 'Winner unchanged'}</span>
        </div>
        {nr.changed && nr.before && nr.after && <p style={{ margin: 0 }}>The next ₹1 moves from <b>{nameOf(nr.before)}</b> to <b>{nameOf(nr.after)}</b>{nr.reason ? <>, because {nameOf(nr.before)} is now {nr.reason.replace(/\.$/, '').replace(/^Blocked by policy: /, 'blocked: ').replace(/^./, (c) => c.toLowerCase())}</> : null}.</p>}
        {nr.changed && !nr.after && <p style={{ margin: 0 }}>No campaign clears the guardrails under this scenario, so the engine holds budget.</p>}
        {sameCampaign && <p style={{ margin: 0 }}><b>{nameOf(nr.after)}</b> still wins the next ₹1. Profit per ₹1 {Math.abs(dp) < 0.005 ? 'is unchanged' : `${dp > 0 ? 'rises' : 'falls'} from ${fx(nr.before.profit_per_rupee)} to ${fx(nr.after.profit_per_rupee)}`}.</p>}
      </div>
      <div className="grid g3">
        <div className="card kpi"><div className="label">Scenario profit gain</div><div className="value up num">{plus(t.incremental_profit)}</div><div className="muted small">per day · {compact(t.incremental_profit_30d)} / 30d</div></div>
        <div className="card kpi"><div className="label">vs baseline</div><div className={'value num ' + (res.profit_delta >= 0 ? 'up' : 'down')}>{plus(res.profit_delta)}</div><div className="muted small">per day</div></div>
        <div className="card kpi"><div className="label">Total budget</div><div className="value num">{inr(t.budget_after)}</div><div className="muted small">{t.budget_after === t.budget_before ? 'unchanged' : plus(t.budget_after - t.budget_before) + ' vs today'}</div></div>
      </div>
      <div className="card disc-card">
        <Disclosure title="Budget moves" summary={res.narrative.slice(0, 80) + (res.narrative.length > 80 ? '…' : '')}>
          <p className="muted" style={{ marginTop: 0 }}>{res.narrative}</p>
          <table className="table"><tbody>
            {res.scenario.recommendations.slice(0, 6).map((r) => (
              <tr key={r.rec_id}><td>{r.title}</td><td className="r up num">{plus(r.expected_profit)}/day</td><td className="r muted num">{pct(r.confidence)}</td></tr>
            ))}
            {!res.scenario.recommendations.length && <tr><td className="muted">None.</td></tr>}
          </tbody></table>
        </Disclosure>
        <Disclosure title="Allocation · baseline vs scenario" summary={`${chart.length} campaigns`}>
          <div role="img" aria-label="Bar chart comparing baseline and scenario daily budget for each campaign">
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
        </Disclosure>
      </div>
    </>
  )
}
