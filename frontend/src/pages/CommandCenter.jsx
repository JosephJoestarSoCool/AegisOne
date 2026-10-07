import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { compact, inr, pct, plus, useApi } from '../api'
import { C, KIND_TONE, Kpi, Loading, RecCard, Tip, axis } from '../components'

export default function CommandCenter({ company, go }) {
  const { data, error, loading, reload } = useApi('/overview', { company_id: company })
  if (!data) return <div className="page"><Loading error={error} /></div>
  const k = data.kpis, d = data.kpi_delta, rc = data.reconciliation
  const top = data.top_recommendations[0]
  return (
    <div className="page">
      <div className="card hero">
        <div className="row between wrap" style={{ marginBottom: 14 }}>
          <div>
            <div className="muted small" style={{ fontWeight: 600, letterSpacing: '.05em', textTransform: 'uppercase' }}>Where the next ₹1 should go</div>
            <div className="big num" style={{ marginTop: 6 }}>
              <span className="up">{plus(data.incremental_profit)}</span><span className="muted" style={{ fontSize: 16, fontWeight: 500 }}> / day identified</span>
            </div>
            <div className="muted">≈ {compact(data.incremental_profit_30d)} over 30 days at the <b style={{ color: 'var(--text)' }}>same total ad spend</b> — {data.top_recommendations.length > 0 ? 'top actions below' : 'no moves clear the guardrails'}.</div>
          </div>
          <div className="stack" style={{ gap: 6, textAlign: 'right' }}>
            <span className="pill red">Platforms over-claim orders by {pct(rc.overcount_pct)}</span>
            <span className="pill">Reported ROAS {rc.reported_roas.toFixed(2)} → reconciled <b className="gold">{rc.reconciled_roas.toFixed(2)}</b></span>
          </div>
        </div>
        {top ? <RecCard rec={top} top onDecided={reload} expanded={false} /> : <div className="empty">Portfolio is already at its optimum under this policy.</div>}
      </div>

      <div className="grid g4">
        <Kpi label="Revenue (7d)" value={compact(k.revenue)} delta={d.revenue} />
        <Kpi label="Ad spend (7d)" value={compact(k.spend)} delta={d.spend} invert />
        <Kpi label="Profit after ads (7d)" value={compact(k.profit)} delta={d.profit} />
        <Kpi label="ROAS · reconciled" value={k.roas.toFixed(2) + '×'} delta={d.roas} />
      </div>

      <div className="grid g-7-5">
        <div className="card">
          <h3>30-day trend · revenue, spend, profit</h3>
          <ResponsiveContainer width="100%" height={270}>
            <ComposedChart data={data.trend} margin={{ left: 0, right: 8, top: 8 }}>
              <defs><linearGradient id="rev" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={C.gold} stopOpacity={0.35} /><stop offset="100%" stopColor={C.gold} stopOpacity={0} /></linearGradient></defs>
              <CartesianGrid stroke={C.line} vertical={false} />
              <XAxis dataKey="date" {...axis} tickFormatter={(v) => v.slice(5)} interval={4} />
              <YAxis {...axis} tickFormatter={compact} width={64} />
              <Tooltip content={<Tip fmt={(v) => inr(v)} />} />
              <Area dataKey="revenue" name="Revenue" stroke={C.gold} fill="url(#rev)" strokeWidth={2} isAnimationActive={false} />
              <Line dataKey="spend" name="Spend" stroke={C.red} dot={false} strokeWidth={2} isAnimationActive={false} />
              <Line dataKey="profit" name="Profit" stroke={C.teal} dot={false} strokeWidth={2} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <div className="card">
          <div className="row between"><h3>Anomalies · {data.anomaly_count}</h3><button className="btn ghost small" onClick={() => go('diagnosis')}>Diagnose →</button></div>
          <div className="stack" style={{ gap: 4 }}>
            {data.anomalies.map((a) => (
              <button key={a.anomaly_id} className="list-item" onClick={() => go('diagnosis', a.anomaly_id)}>
                <div className="row between"><b style={{ fontSize: 13 }}>{a.title}</b><span className="sev"><i style={{ width: a.severity * 100 + '%' }} /></span></div>
                <div className="row"><span className={'pill ' + (KIND_TONE[a.kind] || '')}>{a.kind.replace(/_/g, ' ')}</span><span className="muted small">{pct(a.confidence)} confident</span></div>
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="row between"><h3>Top opportunities · policy-adjusted marginal return</h3><button className="btn ghost small" onClick={() => go('optimizer')}>Open optimizer →</button></div>
        <table className="table">
          <thead><tr><th>Campaign</th><th>Platform</th><th className="r">ROAS</th><th className="r">Marginal ROAS</th><th className="r">Budget</th><th style={{ width: 180 }}>Opportunity</th></tr></thead>
          <tbody>
            {data.opportunities.map((o) => (
              <tr key={o.campaign_id}>
                <td><b>{o.name}</b>{o.anomaly && <span className="pill red" style={{ marginLeft: 8 }}>{o.anomaly.replace(/_/g, ' ')}</span>}</td>
                <td className="muted">{o.platform}</td>
                <td className="r num">{o.roas.toFixed(2)}</td>
                <td className="r num">{o.marginal_roas.toFixed(2)}</td>
                <td className="r num">{inr(o.current)}</td>
                <td><div className="row"><div className="bar" style={{ flex: 1 }}><i style={{ width: '100%', transform: `scaleX(${o.opportunity_score / 100})` }} /></div><b className="num">{o.opportunity_score}</b></div></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {loading && <span className="muted small">refreshing…</span>}
    </div>
  )
}
