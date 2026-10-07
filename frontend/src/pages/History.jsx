import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { compact, inr, pct, plus, useApi } from '../api'
import { C, Loading, Tip, TYPE_LABEL, axis } from '../components'

export default function History({ company }) {
  const { data, error } = useApi('/history', { company_id: company })
  if (!data) return <div className="page"><Loading error={error} /></div>
  const s = data.summary
  const done = data.items.filter((i) => i.actual_profit !== null).slice().reverse()
  const chart = done.map((i, n) => ({ n: n + 1, label: i.created_at.slice(5, 10), Predicted: i.expected_profit, Actual: i.actual_profit }))
  return (
    <div className="page">
      <div className="grid g4">
        <div className="card kpi"><div className="label">Decisions</div><div className="value num">{s.decisions}</div><div className="muted small">{s.approved} approved</div></div>
        <div className="card kpi"><div className="label">Predicted vs actual</div><div className="value num">{compact(s.actual_total)}<span className="muted" style={{ fontSize: 14 }}> / {compact(s.predicted_total)}</span></div><div className="muted small">realised / forecast profit per day</div></div>
        <div className="card kpi"><div className="label">Mean absolute error</div><div className="value num">{pct(s.mean_abs_error_pct, 1)}</div><div className="muted small">forecast error across scored decisions</div></div>
        <div className="card kpi"><div className="label">Avg. updated confidence</div><div className="value gold num">{pct(s.avg_confidence)}</div><div className="muted small">after learning from outcomes</div></div>
      </div>
      <div className="grid g-8-4">
        <div className="card">
          <h3>Prediction vs outcome</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={chart} margin={{ left: 0, right: 8 }}>
              <CartesianGrid stroke={C.line} vertical={false} />
              <XAxis dataKey="label" {...axis} /><YAxis {...axis} tickFormatter={compact} width={56} />
              <Tooltip content={<Tip fmt={(v) => inr(v)} />} cursor={{ fill: 'rgba(255,255,255,.04)' }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="Predicted" fill="#3a4a6d" radius={3} isAnimationActive={false} />
              <Bar dataKey="Actual" fill={C.teal} radius={3} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="card">
          <h3>Calibration by action type</h3>
          <div className="stack">
            {data.calibration.map((c) => (
              <div key={c.rec_type}>
                <div className="row between small"><span>{TYPE_LABEL[c.rec_type] || c.rec_type}</span><span className="muted num">{pct(c.accuracy)} · n={c.n}</span></div>
                <div className="bar" style={{ marginTop: 4 }}><i style={{ width: '100%', transform: `scaleX(${c.accuracy})`, background: c.accuracy > 0.8 ? C.teal : C.gold }} /></div>
              </div>
            ))}
          </div>
          <div className="muted small" style={{ marginTop: 12 }}>New recommendations of each type inherit this accuracy: confidence × (0.75 + 0.25·accuracy).</div>
        </div>
      </div>
      <div className="card">
        <h3>Decision log · prediction → action → outcome → error → confidence</h3>
        <table className="table">
          <thead><tr><th>Date</th><th>Action</th><th className="r">Predicted</th><th className="r">Actual</th><th className="r">Error</th><th className="r">Confidence</th><th>Status</th></tr></thead>
          <tbody>{data.items.map((i) => (
            <tr key={i.rec_id}>
              <td className="muted num">{i.created_at.slice(0, 10)}</td>
              <td><span className="pill" style={{ marginRight: 8 }}>{TYPE_LABEL[i.rec_type] || i.rec_type}</span>{i.title}</td>
              <td className="r num">{plus(i.expected_profit)}</td>
              <td className="r num">{i.actual_profit !== null ? plus(i.actual_profit) : '—'}</td>
              <td className={'r num ' + (i.error_pct === null ? 'muted' : i.error_pct < 0 ? 'down' : 'up')}>{i.error_pct !== null ? (i.error_pct * 100).toFixed(1) + '%' : '—'}</td>
              <td className="r num">{i.confidence_after !== null ? <>{pct(i.confidence_before)} → <b className="gold">{pct(i.confidence_after)}</b></> : pct(i.confidence)}</td>
              <td><span className={'pill ' + (i.status === 'approved' ? 'teal' : '')}>{i.status}</span></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  )
}
