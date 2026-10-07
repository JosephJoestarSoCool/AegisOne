import { useState } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { inr, pct, useApi } from '../api'
import { Loading, Ring, Tip } from '../components'
import { C, KIND_TONE, TYPE_LABEL, axis } from '../lib'

function Series({ company, campaignId }) {
  const { data } = useApi('/campaign-series', { company_id: company, campaign_id: campaignId })
  if (!data) return <div className="loading">Loading series…</div>
  const s = data.series
  const base = s.slice(0, 25)
  const mean = (k) => base.reduce((a, r) => a + r[k], 0) / base.length
  const idx = s.map((r) => ({
    date: r.date, ROAS: (r.roas / mean('roas')) * 100, CTR: (r.ctr / mean('ctr')) * 100, CPC: (r.cpc / mean('cpc')) * 100,
    Conversion: (r.cvr / mean('cvr')) * 100, Frequency: (r.frequency / mean('frequency')) * 100,
  }))
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={idx} margin={{ left: 0, right: 8, top: 8 }}>
        <CartesianGrid stroke={C.line} vertical={false} />
        <XAxis dataKey="date" {...axis} tickFormatter={(v) => v.slice(5)} interval={5} />
        <YAxis {...axis} width={40} />
        <ReferenceLine y={100} stroke={C.muted} strokeDasharray="3 3" />
        <Tooltip content={<Tip fmt={(v) => v.toFixed(0)} />} />
        <Line dataKey="ROAS" stroke={C.red} strokeWidth={2.5} dot={false} isAnimationActive={false} />
        <Line dataKey="CTR" stroke={C.gold} strokeWidth={2} dot={false} isAnimationActive={false} />
        <Line dataKey="CPC" stroke={C.blue} strokeWidth={2} dot={false} isAnimationActive={false} />
        <Line dataKey="Conversion" stroke={C.muted} strokeWidth={1.5} dot={false} isAnimationActive={false} />
        <Line dataKey="Frequency" stroke={C.violet} strokeWidth={1.5} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}

export default function Diagnosis({ company, focus, go }) {
  const { data, error } = useApi('/diagnosis', { company_id: company })
  const [sel, setSel] = useState(focus || null)   // page remounts per company/navigation, so focus seeds state
  if (!data) return <div className="page"><Loading error={error} /></div>
  const list = data.anomalies
  const a = list.find((x) => x.anomaly_id === sel) || list[0]
  if (!a) return <div className="page"><div className="empty card">No anomalies detected. Metrics are inside their normal bands.</div></div>
  const recs = data.recommendations.filter((r) => r.source_campaign_id === a.campaign_id || r.target_campaign_id === a.campaign_id).slice(0, 3)
  return (
    <div className="page">
      <div className="grid g-4-8" style={{ alignItems: 'start' }}>
        <div className="card" style={{ padding: 10 }}>
          <h3 style={{ padding: '8px 10px 0' }}>Detected · {list.length}</h3>
          <div className="stack" style={{ gap: 2 }}>
            {list.map((x) => (
              <button key={x.anomaly_id} className="list-item" aria-current={x.anomaly_id === a.anomaly_id ? 'true' : undefined} onClick={() => setSel(x.anomaly_id)}>
                <div className="row between"><b style={{ fontSize: 13 }}>{x.title}</b><span className="sev"><i style={{ width: x.severity * 100 + '%' }} /></span></div>
                <div className="row"><span className={'pill ' + (KIND_TONE[x.kind] || '')}>{x.kind.replace(/_/g, ' ')}</span><span className="muted small num">{pct(x.confidence)}</span></div>
              </button>
            ))}
          </div>
        </div>

        <div className="stack stagger" key={a.anomaly_id}>
          <div className="card">
            <div className="row between wrap" style={{ marginBottom: 14 }}>
              <div><span className={'pill ' + (KIND_TONE[a.kind] || '')}>{a.kind.replace(/_/g, ' ')}</span><h2 style={{ fontSize: 20, marginTop: 8, letterSpacing: '-0.01em' }}>{a.title}</h2></div>
              <div className="row"><div style={{ textAlign: 'right' }}><div className="muted small">confidence</div><div className="muted small">{a.level === 'campaign' ? 'rule-scored hypotheses' : 'signal strength'}</div></div><Ring value={a.confidence} /></div>
            </div>
            <div className="grid g2">
              <div className="stack" style={{ gap: 14 }}>
                <Step n="1" label="What happened" color={C.red}>{a.what_happened}</Step>
                <Step n="2" label="Probable cause" color={C.gold}>{a.probable_cause}</Step>
              </div>
              <div className="stack" style={{ gap: 14 }}>
                <Step n="3" label="Confidence" color={C.teal}>{pct(a.confidence)} — {a.alternatives?.length ? 'rivals considered: ' + a.alternatives.map((x) => `${x.cause.split(' (')[0]} ${pct(x.confidence)}`).join(', ') : 'no competing hypothesis scored above threshold.'}</Step>
                <Step n="4" label="Recommended action" color={C.blue}>{a.recommended_action}</Step>
              </div>
            </div>
            {a.daily_value_at_risk > 0 && <div className="muted small" style={{ marginTop: 12 }}>≈ <b className="down num">{inr(a.daily_value_at_risk)}</b> of daily ad value currently at risk.</div>}
          </div>

          <div className="grid g-7-5">
            <div className="card">
              <h3>{a.campaign_id ? 'Signal trace · indexed to 25-day baseline = 100' : 'Evidence'}</h3>
              {a.campaign_id ? <Series company={company} campaignId={a.campaign_id} /> : <div className="muted">Inventory / pricing anomalies are measured against policy thresholds — see the evidence table.</div>}
              <div className="row wrap small" style={{ gap: 14, marginTop: 8 }}>
                {[['ROAS', C.red], ['CTR', C.gold], ['CPC', C.blue], ['Conversion', C.muted], ['Frequency', C.violet]].map(([n, c]) => <span key={n} className="row" style={{ gap: 6 }}><i className="dot" style={{ background: c }} />{n}</span>)}
              </div>
            </div>
            <div className="card">
              <h3>Evidence</h3>
              <div className="tscroll" tabIndex={0} role="region" aria-label="Evidence table, scrollable"><table className="table">
                <thead><tr><th>Metric</th><th className="r">Baseline</th><th className="r">Now</th><th className="r">Δ</th></tr></thead>
                <tbody>{a.evidence.map((e) => (
                  <tr key={e.label}><td>{e.label}</td><td className="r num muted">{e.baseline}</td><td className="r num">{e.current}</td>
                    <td className={'r num ' + (e.change_pct === 0 ? 'muted' : Math.abs(e.change_pct) < 12 ? 'muted' : 'down')}>{e.change_pct ? (e.change_pct > 0 ? '+' : '') + e.change_pct + '%' : '—'}</td></tr>
                ))}</tbody>
              </table></div>
            </div>
          </div>

          {recs.length > 0 && (
            <div className="card">
              <div className="row between"><h3>Decisions this triggers</h3><button className="btn ghost small" onClick={() => go('optimizer')}>Review in optimizer →</button></div>
              {recs.map((r) => (
                <div key={r.rec_id} className="row between wrap" style={{ padding: '8px 0', borderTop: '1px solid var(--line)' }}>
                  <div><span className="pill" style={{ marginRight: 8 }}>{TYPE_LABEL[r.rec_type]}</span>{r.title}</div>
                  <b className="up num">+{inr(r.expected_profit)}/day</b>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function Step({ n, label, color, children }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '26px 1fr', gap: 10 }}>
      <div style={{ width: 24, height: 24, borderRadius: '50%', background: color, color: '#0a101e', fontWeight: 800, display: 'grid', placeItems: 'center', fontSize: 12 }}>{n}</div>
      <div><div className="muted small" style={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 3 }}>{label}</div><div>{children}</div></div>
    </div>
  )
}
