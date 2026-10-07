import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { compact, inr, plus, useApi } from '../api'
import { Kpi, Loading, RecCard, Tip } from '../components'
import { C, axis, shortName } from '../lib'

export default function Optimizer({ company }) {
  const { data, error, reload } = useApi('/plan', { company_id: company })
  if (!data) return <div className="page"><Loading error={error} /></div>
  const t = data.totals
  const chart = data.allocation.map((a) => ({ name: shortName(a.name), Current: a.current, Recommended: a.recommended }))
  return (
    <div className="page">
      <div className="grid g4">
        <Kpi label="Daily budget" value={inr(t.budget_after)} />
        <div className="card kpi"><div className="label">Budget moved</div><div className="value num">{inr(t.moved)}</div><div className="muted small">{((t.moved / t.budget_before) * 100).toFixed(0)}% of total · total spend unchanged</div></div>
        <div className="card kpi"><div className="label">Expected incremental profit</div><div className="value up num">{plus(t.incremental_profit)}</div><div className="muted small">per day</div></div>
        <div className="card kpi"><div className="label">30-day impact</div><div className="value up num">{compact(t.incremental_profit_30d)}</div><div className="muted small">model estimate · {data.policy.name} policy</div></div>
      </div>

      <div className="card">
        <h3>Current vs recommended daily allocation</h3>
        <ResponsiveContainer width="100%" height={Math.max(300, data.allocation.length * 34)}>
          <BarChart data={chart} layout="vertical" margin={{ left: 16, right: 16 }} barCategoryGap={6}>
            <CartesianGrid stroke={C.line} horizontal={false} />
            <XAxis type="number" {...axis} tickFormatter={compact} />
            <YAxis type="category" dataKey="name" {...axis} width={170} />
            <Tooltip content={<Tip fmt={(v) => inr(v)} />} cursor={{ fill: 'rgba(255,255,255,.04)' }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="Current" fill="#3a4a6d" radius={3} isAnimationActive={false} />
            <Bar dataKey="Recommended" fill={C.gold} radius={3} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div>
        <div className="row between" style={{ marginBottom: 12 }}><h3 style={{ margin: 0 }}>Recommendations · ranked by expected incremental profit</h3><span className="muted small">{data.recommendations.length} actions</span></div>
        <div className="stack">
          {data.recommendations.map((r, i) => <RecCard key={r.rec_id} rec={r} top={i === 0} onDecided={reload} expanded={false} />)}
          {!data.recommendations.length && <div className="card empty">No move clears the guardrails under this policy.</div>}
        </div>
      </div>

      <div className="card">
        <h3>Allocation detail</h3>
        <table className="table">
          <thead><tr><th>Campaign</th><th className="r">Current</th><th className="r">Recommended</th><th className="r">Δ</th><th className="r">ROAS</th><th className="r">Marg. ROAS</th><th className="r">Marg. profit/₹</th><th style={{ width: 130 }}>Opportunity</th></tr></thead>
          <tbody>{data.allocation.map((a) => (
            <tr key={a.campaign_id}>
              <td><b>{a.name}</b>{a.action === 'pause' && <span className="pill red" style={{ marginLeft: 8 }}>paused</span>}{!a.eligible && a.action !== 'pause' && <span className="pill" style={{ marginLeft: 8 }} title="Fails a guardrail for scaling">gated</span>}</td>
              <td className="r num">{inr(a.current)}</td><td className="r num">{inr(a.recommended)}</td>
              <td className={'r num ' + (a.delta > 0 ? 'up' : a.delta < 0 ? 'down' : 'muted')}>{a.delta ? plus(a.delta) : '—'}</td>
              <td className="r num">{a.roas.toFixed(2)}</td><td className="r num">{a.marginal_roas.toFixed(2)}</td>
              <td className={'r num ' + (a.marginal_profit_per_rupee < 0 ? 'down' : '')}>{a.marginal_profit_per_rupee.toFixed(2)}</td>
              <td><div className="bar"><i style={{ width: '100%', transform: `scaleX(${a.opportunity_score / 100})` }} /></div></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  )
}
