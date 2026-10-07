import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { compact, inr, pct, useApi } from '../api'
import { useState } from 'react'
import { C, KIND_TONE, Kpi, Loading, RecCard, Tip, axis } from '../components'
import { CandidateDrawer, Portfolio, TrapCard, Verdict, WhyNot } from '../decision'
import { Drawer } from '../ui'

export default function CommandCenter({ company, go }) {
  const { data, error, loading, reload } = useApi('/overview', { company_id: company })
  const [sel, setSel] = useState(null)
  const [review, setReview] = useState(false)
  if (!data) return <div className="page"><Loading error={error} /></div>
  const k = data.kpis, d = data.kpi_delta, rc = data.reconciliation
  const top = data.top_recommendations[0]
  const w = data.next_rupee
  return (
    <div className="page">
      <Verdict w={w} company={data.company.name} hasRec={!!top} onReview={() => setReview(true)} onOpen={setSel} />
      <div className="grid g-7-5">
        <WhyNot alts={w?.alternatives} onOpen={setSel} />
        <TrapCard trap={data.roas_trap} candidates={data.candidates} />
      </div>
      <Portfolio rows={data.candidates} winnerId={w?.campaign_id} onOpen={setSel} />
      <Drawer open={review && !!top} onClose={() => setReview(false)} title="Recommended action" kicker="Review & approve">
        {top && <RecCard rec={top} top onDecided={reload} expanded={false} />}
      </Drawer>
      <CandidateDrawer x={sel} winner={w} onClose={() => setSel(null)} />

      <div className="grid g4">
        <Kpi label="Revenue (7d)" value={compact(k.revenue)} delta={d.revenue} />
        <Kpi label="Ad spend (7d)" value={compact(k.spend)} delta={d.spend} invert />
        <Kpi label="Profit after ads (7d)" value={compact(k.profit)} delta={d.profit} />
        <Kpi label="ROAS · reconciled" value={k.roas.toFixed(2) + '×'} delta={d.roas} />
      </div>

      <div className="row wrap recon">
        <span className="pill red">Platforms over-claim orders by {pct(rc.overcount_pct)}</span>
        <span className="pill">Reported ROAS {rc.reported_roas.toFixed(2)} → reconciled <b className="gold">{rc.reconciled_roas.toFixed(2)}</b></span>
        <span className="muted small">All figures use reconciled orders.</span>
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

      {loading && <span className="muted small">refreshing…</span>}
    </div>
  )
}
