import { useEffect, useMemo, useRef, useState } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { compact, inr, pct, plus, useApi } from './api'
import { ErrorState, Loading } from './components'
import { SectionLabel } from './editorial'

/**
 * Projected Impact: ACTUAL (real history) -> APPROVED (the moment of approval) -> PROJECTED (the approved recommendation's own
 * engine output) -> OBSERVED (the feedback engine's simulated outcome, on request).
 * All numbers come from /api/projected-impact (real reconciled history + the optimizer's recommendation) and from the
 * feedback engine's decision response. Nothing here is generated in the browser except arithmetic on those values.
 */

const fmt = (key, v) => (v == null ? '—' : key === 'roas' ? v.toFixed(2) + '×' : compact(v))
const LEGEND = [
  ['actual', 'Actual', 'solid'], ['projected', 'Projected', 'dashed'], ['baseline', 'No-action baseline', 'dotted'], ['observed', 'Observed (simulated outcome)', 'solid accent'],
]

function Swatch({ kind }) {
  return <svg width="30" height="8" aria-hidden="true" className={'pi-sw ' + kind.replace(' ', '-')}><line x1="0" y1="4" x2="30" y2="4" /></svg>
}

function ApprovedLabel({ viewBox }) {
  const { x, y } = viewBox
  return (
    <g>
      <rect x={x - 38} y={y} width="76" height="18" fill="#efece4" />
      <text x={x} y={y + 13} textAnchor="middle" className="pi-approved-t">APPROVED</text>
    </g>
  )
}

function ChartTip({ active, payload, label, metric }) {
  if (!active || !payload?.length) return null
  const rows = payload.filter((p) => p.value != null)
  return (
    <div className="tt pi-tip">
      <b>{label}</b>
      {rows.map((p) => <div key={p.dataKey} className="num"><span className="muted">{LABEL[p.dataKey]}</span> {fmt(metric, p.value)}</div>)}
    </div>
  )
}
const LABEL = { actual: 'Actual', projected: 'Projected', baseline: 'No-action baseline', observed: 'Observed (simulated)' }

export default function ProjectedImpact({ company, rec, result }) {
  const { data, error } = useApi('/projected-impact', { company_id: company, rec_id: rec.rec_id })
  const [metric, setMetric] = useState('profit')
  const [observed, setObserved] = useState(false)
  const root = useRef(null)

  useEffect(() => {                         // bring the reveal into view (no motion if the user prefers none)
    const calm = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    root.current?.scrollIntoView?.({ behavior: calm ? 'auto' : 'smooth', block: 'nearest' })
  }, [data])

  const rows = useMemo(() => {
    if (!data) return []
    const last = data.history[data.history.length - 1]
    const out = data.history.map((h) => ({ date: h.date, actual: h[metric] }))
    const join = out[out.length - 1]
    join.projected = join.baseline = last[metric]
    if (metric === 'profit' && result) join.observed = last[metric]
    for (const p of data.projection) {
      const row = { date: p.date, projected: p[metric], baseline: p['base_' + metric] }
      if (metric === 'profit' && result) row.observed = (data.run_rate.profit + result.actual_profit) * p.profit_shape
      out.push(row)
    }
    return out
  }, [data, metric, result])

  if (error) return <section className="pi" ref={root}><ErrorState error={error} what="the projected impact" /></section>
  if (!data) return <section className="pi" ref={root}><Loading /></section>

  const r = data.rec
  const moved = r.amount > 0 ? `${inr(r.amount)}/day moved` : r.title
  const showObs = observed && metric === 'profit' && result
  const asOf = data.as_of
  const defs = data.metrics.find((m) => m.key === metric)
  const summary = `Chart of ${defs.label.toLowerCase()}: ${data.history.length} actual days up to ${asOf}, the approval point on ${asOf}, then a ${data.horizon_days}-day projection. Values are in the data table below.`
  return (
    <section className="pi reveal" ref={root} aria-labelledby="pi-h">
      <header className="pi-head">
        <div>
          <SectionLabel>Projected impact</SectionLabel>
          <h3 id="pi-h" className="pi-title">Actual performance → approved decision → projected trajectory</h3>
        </div>
        <span className="pi-stamp" role="status">Approved</span>
      </header>

      <dl className="pi-facts">
        <div><dt>Actual</dt><dd>Last {data.history.length} days</dd></div>
        <div><dt>Approved</dt><dd>{moved}</dd></div>
        <div><dt>Projected</dt><dd>Next {data.horizon_days} days</dd></div>
        <div className="pi-big"><dt>Expected incremental contribution profit</dt><dd className="num up">{plus(r.expected_profit)}<small>/day</small></dd></div>
        <div><dt>Confidence</dt><dd className="num">{pct(r.confidence)}</dd></div>
      </dl>

      <div className="pi-controls">
        <div className="seg" role="group" aria-label="Chart metric">
          {data.metrics.map((m) => (
            <button key={m.key} type="button" aria-pressed={metric === m.key} onClick={() => setMetric(m.key)}>{m.label}</button>
          ))}
        </div>
        <ul className="pi-legend" aria-label="Legend">
          {LEGEND.filter(([k]) => k !== 'observed' || showObs).map(([k, label, kind]) => <li key={k}><Swatch kind={kind} />{label}</li>)}
        </ul>
      </div>

      <div className="pi-chart" role="img" aria-label={summary}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 28, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="rgba(239,236,228,0.12)" />
            <XAxis dataKey="date" tickFormatter={(d) => d.slice(5)} stroke="#8e8b83" fontSize={11} tickLine={false} axisLine={{ stroke: 'rgba(239,236,228,0.3)' }} minTickGap={28} />
            <YAxis tickFormatter={(v) => fmt(metric, v)} stroke="#8e8b83" fontSize={11} tickLine={false} axisLine={false} width={64} domain={['auto', 'auto']} />
            <Tooltip content={<ChartTip metric={metric} />} cursor={{ stroke: 'rgba(239,236,228,0.35)' }} />
            <ReferenceLine x={asOf} stroke="#efece4" strokeWidth={1.5} label={<ApprovedLabel />} />
            <Line type="monotone" dataKey="baseline" stroke="#8e8b83" strokeWidth={1.5} strokeDasharray="1 5" strokeLinecap="round" dot={false} isAnimationActive={false} connectNulls />
            <Line type="monotone" dataKey="projected" stroke="#efece4" strokeWidth={2.2} strokeDasharray="8 5" dot={false} isAnimationActive={false} connectNulls />
            <Line type="monotone" dataKey="actual" stroke="#efece4" strokeWidth={2.4} dot={false} isAnimationActive={false} />
            {showObs && <Line type="monotone" dataKey="observed" stroke="var(--accent)" strokeWidth={2.6} dot={false} isAnimationActive={false} connectNulls />}
          </LineChart>
        </ResponsiveContainer>
        <span className="pi-zone a" aria-hidden="true">Actual</span>
        <span className="pi-zone p" aria-hidden="true">Projected · {data.horizon_days} days</span>
      </div>
      <p className="pi-note">Projected values are an estimate, not results. {defs.derived ? 'Derived from projected profit and spend using the history’s blended margin. ' : ''}{metric === 'spend' && r.amount > 0 && data.increment.spend === 0 ? 'Total spend is unchanged by a budget move. ' : ''}Both projected lines start from the {data.run_rate.days}-day run-rate, so the step at the marker reflects the run-rate; the effect of the decision is the gap between Projected and the No-action baseline.</p>

      <div className="pi-feedback">
        <SectionLabel>Feedback → learn</SectionLabel>
        {!observed ? (
          <div className="row wrap">
            <button type="button" className="btn small" onClick={() => setObserved(true)}>Reveal simulated outcome</button>
            <span className="muted small">The feedback engine simulates what happened and scores the prediction. It is not live ad data.</span>
          </div>
        ) : (
          <dl className="pi-facts pi-obs">
            <div><dt>Projected</dt><dd className="num">{plus(result.predicted_profit)}<small>/day</small></dd></div>
            <div><dt>Observed (simulated)</dt><dd className="num up">{plus(result.actual_profit)}<small>/day</small></dd></div>
            <div><dt>Prediction error</dt><dd className={'num ' + (result.error < 0 ? 'down' : 'up')}>{(result.error_pct * 100).toFixed(1)}%</dd></div>
            <div><dt>Confidence after learning</dt><dd className="num">{pct(result.confidence_before)} → {pct(result.confidence_after)}</dd></div>
          </dl>
        )}
        {observed && metric !== 'profit' && <p className="pi-note">The observed outcome is tracked for contribution profit only. Switch to Contribution profit to see it on the chart.</p>}
      </div>

      <details className="pi-table">
        <summary>View chart data as a table</summary>
        <div className="tscroll" tabIndex={0} role="region" aria-label="Chart data table, scrollable">
          <table className="table">
            <thead><tr><th>Date</th><th className="r">Actual</th><th className="r">Projected</th><th className="r">No-action baseline</th>{showObs && <th className="r">Observed (simulated)</th>}</tr></thead>
            <tbody>{rows.map((x) => (
              <tr key={x.date}><td>{x.date}</td><td className="r num">{fmt(metric, x.actual)}</td><td className="r num">{fmt(metric, x.projected)}</td><td className="r num">{fmt(metric, x.baseline)}</td>{showObs && <td className="r num">{fmt(metric, x.observed)}</td>}</tr>
            ))}</tbody>
          </table>
        </div>
      </details>
    </section>
  )
}
