import { useState } from 'react'
import { inr, pct, plus, post, retryAll } from './api'
import { C, TYPE_LABEL, errorText } from './lib'


export function Kpi({ label, value, delta, invert }) {
  const good = invert ? delta < 0 : delta > 0
  return (
    <div className="card kpi">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {delta !== undefined && (
        <div className={'delta ' + (Math.abs(delta) < 0.005 ? 'muted' : good ? 'up' : 'down')}>
          {delta > 0 ? '▲' : delta < 0 ? '▼' : '•'} {Math.abs(delta * 100).toFixed(1)}% <span className="muted">vs prior 7d</span>
        </div>
      )}
    </div>
  )
}

export function Ring({ value }) {
  return (
    <div className="ring" style={{ '--p': value }}>
      <span>{Math.round(value * 100)}%</span>
    </div>
  )
}

export function Tip({ active, payload, label, fmt = (v) => v }) {
  if (!active || !payload?.length) return null
  return (
    <div className="tt">
      <div className="muted" style={{ marginBottom: 4 }}>{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ color: p.color || p.fill }}>
          {p.name}: <b>{fmt(p.value, p.name)}</b>
        </div>
      ))}
    </div>
  )
}

const TYPE_TONE = { move_budget: 'gold', increase_budget: 'teal', decrease_budget: 'red', pause_campaign: 'red', replace_creative: 'violet' }

/** Full recommendation card: flow, why, policy drivers, guardrails, approve/reject → feedback. */
export function RecCard({ rec, top, onDecided, expanded = true, actions = true }) {
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const [status, setStatus] = useState(rec.status)
  const [more, setMore] = useState(expanded)
  const decide = async (approve) => {
    setBusy(true)
    try {
      const r = await post('/recommendations/decide', { recommendation: rec, approve })
      setStatus(r.status)
      setResult(r)
      onDecided?.(r)
    } finally { setBusy(false) }
  }
  const done = status !== 'pending'
  return (
    <div className={'card rec' + (top ? ' top' : '')}>
      <div className="row between wrap">
        <div className="row wrap">
          <span className={'pill ' + (TYPE_TONE[rec.rec_type] || '')}>{TYPE_LABEL[rec.rec_type]}</span>
          {rec.relation_label && <span className="pill">{rec.relation_label}</span>}
          {rec.source_anomaly && <span className="pill red">fixes {rec.source_anomaly.replace(/_/g, ' ')}</span>}
        </div>
        <div className="row">
          <span className="muted small">confidence</span>
          <b className="num">{pct(rec.confidence)}</b>
        </div>
      </div>
      <div className="title">{rec.title}</div>
      {rec.amount > 0 && rec.source_name && rec.target_name && (
        <div className="flow">
          <div className="node"><small>From</small>{rec.source_name}</div>
          <div className="arrow">→</div>
          <div className="node"><small>To</small>{rec.target_name}</div>
          <div className="node" style={{ flex: '0 0 auto', textAlign: 'right' }}>
            <small>Expected incremental profit</small>
            <b className="up num" style={{ fontSize: 20 }}>{plus(rec.expected_profit)}/day</b>
            <div className="muted small num">≈ {inr(rec.expected_profit_30d)} / 30 days</div>
          </div>
        </div>
      )}
      {!(rec.amount > 0 && rec.source_name && rec.target_name) && (
        <div className="row"><b className="up num" style={{ fontSize: 20 }}>{plus(rec.expected_profit)}/day</b><span className="muted small">expected incremental profit</span></div>
      )}
      <div>
        <div className="muted small" style={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 6 }}>Why</div>
        <ul className="why">{(more ? rec.why : rec.why.slice(0, 1)).map((w, i) => <li key={i}>{w}</li>)}</ul>
        {!expanded && rec.why.length > 1 && <button className="link-btn" aria-expanded={more} onClick={() => setMore(!more)}>{more ? 'Show less' : `Show ${rec.why.length - 1} more reasons`}</button>}
      </div>
      {expanded && rec.policy_drivers?.length > 0 && (
        <div className="stack" style={{ gap: 8 }}>
          <div className="muted small" style={{ fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.05em' }}>
            Policy drivers · {rec.policy_name}
          </div>
          {rec.policy_drivers.slice(0, 4).map((d) => (
            <div className="driver" key={d.dim}>
              <span>{d.label} <span className="muted">({pct(d.weight)})</span></span>
              <div className="bar"><i style={{ width: '100%', transform: `scaleX(${Math.max(0.02, d.share)})`, background: d.value >= 0 ? C.teal : C.red }} /></div>
              <span className={'num ' + (d.value >= 0 ? 'up' : 'down')} style={{ textAlign: 'right' }}>{plus(d.value)}</span>
            </div>
          ))}
        </div>
      )}
      {expanded && rec.guardrails?.length > 0 && (
        <div className="row wrap" style={{ gap: 16 }}>
          {rec.guardrails.map((g) => (
            <span className="check" key={g.label}><i className={'dot' + (g.ok ? '' : ' bad')} />{g.label}: <b className="num">{g.value}</b></span>
          ))}
        </div>
      )}
      {actions && (      <div className="row between wrap">
        {done ? (
          <span className={'pill ' + (status === 'approved' ? 'teal' : '')}>{status === 'approved' ? '✓ Approved' : 'Rejected'}</span>
        ) : (
          <div className="row">
            <button className="btn primary" disabled={busy} onClick={() => decide(true)}>Approve &amp; simulate outcome</button>
            <button className="btn ghost" disabled={busy} onClick={() => decide(false)}>Reject</button>
          </div>
        )}
        {result?.actual_profit !== undefined && <Outcome r={result} />}
      </div>
      )}
    </div>
  )
}

export function Outcome({ r }) {
  return (
    <div className="row wrap" style={{ gap: 18 }}>
      <span className="small muted">predicted <b className="num" style={{ color: 'var(--text)' }}>{inr(r.predicted_profit)}</b></span>
      <span className="small muted">actual <b className="num up">{inr(r.actual_profit)}</b></span>
      <span className="small muted">error <b className={'num ' + (r.error < 0 ? 'down' : 'up')}>{(r.error_pct * 100).toFixed(1)}%</b></span>
      <span className="small muted">confidence <b className="num gold">{pct(r.confidence_before)} → {pct(r.confidence_after)}</b></span>
    </div>
  )
}

export function ErrorState({ error, what }) {
  return (
    <div className="err" role="alert">
      <p style={{ margin: 0 }}>{errorText(error, what)}</p>
      <button className="btn small" style={{ marginTop: 10 }} onClick={retryAll}>Try again</button>
    </div>
  )
}

export function Loading({ error }) {
  if (error) return <ErrorState error={error} />
  return (
    <div className="skeleton" role="status" aria-label="Loading">
      <i style={{ height: 190 }} /><div className="grid g-7-5"><i style={{ height: 220 }} /><i style={{ height: 220 }} /></div><i style={{ height: 260 }} />
    </div>
  )
}

