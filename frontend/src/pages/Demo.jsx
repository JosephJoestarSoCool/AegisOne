import { useState } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { inr, pct, plus, post, useApi } from '../api'
import { Loading, Ring, Tip } from '../components'
import { C, axis } from '../lib'

const STEPS = ['Data', 'Diagnosis', 'Decision', 'What-if', 'Feedback']

export default function Demo({ go, setCompany }) {
  const { data, error, reload } = useApi('/demo')
  const [step, setStep] = useState(0)
  const [outcome, setOutcome] = useState(null)
  const [busy, setBusy] = useState(false)
  if (!data) return <div className="page"><Loading error={error} /></div>
  const d1 = data.step1_data, a = data.step2_diagnosis, r = data.step3_decision, w = data.step4_whatif
  const ser = d1.series
  const base = ser.slice(0, 25)
  const mean = (k) => base.reduce((s, x) => s + x[k], 0) / base.length
  const idx = ser.map((x) => ({ date: x.date, ROAS: (x.roas / mean('roas')) * 100, CTR: (x.ctr / mean('ctr')) * 100, CPC: (x.cpc / mean('cpc')) * 100, Conversion: (x.cvr / mean('cvr')) * 100 }))
  const approve = async () => {
    setBusy(true)
    try { setOutcome(await post('/recommendations/decide', { recommendation: r, approve: true })) } finally { setBusy(false) }
  }
  const resetAll = async () => { await post('/reset', {}); setOutcome(null); setStep(0); reload() }
  const next = () => setStep((s) => Math.min(4, s + 1))
  return (
    <div className="page">
      <div className="row between wrap">
        <div>
          <h2 style={{ fontSize: 22, letterSpacing: '-0.02em' }}>Guided demo · a fatigued campaign becomes a profitable decision</h2>
          <div className="muted">Deterministic: {data.step1_data.campaign.name} · Premium Fashion policy</div>
        </div>
        <button className="btn ghost" onClick={resetAll} title="Regenerate data and clear learned feedback">Reset demo</button>
      </div>
      <div className="stepper">
        {STEPS.map((s, i) => (
          <button key={s} aria-current={i === step ? 'step' : undefined} className={i < step ? 'done' : ''} onClick={() => setStep(i)}><i>{i < step ? '✓' : i + 1}</i>{s}</button>
        ))}
      </div>

      {step === 0 && (
        <div className="grid g-5-7 stagger">
          <div className="card stack">
            <h3>1 · Unified business data</h3>
            <div className="grid g2">
              <Mini l="Platforms" v={d1.reconciliation.platforms} /><Mini l="Campaigns" v={d1.reconciliation.campaigns} />
              <Mini l="SKUs" v={d1.reconciliation.skus} /><Mini l="Daily ad rows" v={d1.reconciliation.rows.toLocaleString('en-IN')} />
            </div>
            <div className="card" style={{ background: 'var(--card2)' }}>
              <div className="muted small">Platforms report</div><div className="big num down">{d1.reconciliation.reported_roas.toFixed(2)}× ROAS</div>
              <div className="muted small" style={{ marginTop: 8 }}>After reconciling against the sales ledger</div><div className="big num gold">{d1.reconciliation.reconciled_roas.toFixed(2)}× ROAS</div>
              <div className="muted small" style={{ marginTop: 8 }}>They over-claim orders by <b className="down">{pct(d1.reconciliation.overcount_pct)}</b>.</div>
            </div>
          </div>
          <div className="card">
            <h3>Campaign · {d1.campaign.name}</h3>
            <div className="grid g3" style={{ gap: 12 }}>
              <Mini l="ROAS now" v={d1.campaign.roas.toFixed(2)} tone="down" /><Mini l="CAC" v={inr(d1.campaign.cac)} /><Mini l="Margin" v={pct(d1.campaign.margin)} />
              <Mini l="CTR" v={pct(d1.campaign.ctr, 2)} /><Mini l="CPC" v={inr(d1.campaign.cpc, 1)} /><Mini l="Conversion" v={pct(d1.campaign.cvr, 2)} />
              <Mini l="Daily budget" v={inr(d1.campaign.b0)} /><Mini l="Creative age" v={d1.campaign.creative_age + ' d'} /><Mini l="Marginal ROAS" v={d1.campaign.marginal_roas.toFixed(2)} tone="down" />
            </div>
            <p className="muted" style={{ marginTop: 14 }}>One row per campaign-day, joined to SKU price, margin, stock and competitor price. Every downstream number uses the reconciled orders — not the platform’s claim.</p>
          </div>
        </div>
      )}

      {step === 1 && (
        <div className="grid g-7-5 stagger">
          <div className="card">
            <h3>2 · ROAS just dropped — why?</h3>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={idx} margin={{ left: 0, right: 8 }}>
                <CartesianGrid stroke={C.line} vertical={false} />
                <XAxis dataKey="date" {...axis} tickFormatter={(v) => v.slice(5)} interval={5} /><YAxis {...axis} width={40} />
                <ReferenceLine y={100} stroke={C.muted} strokeDasharray="3 3" />
                <Tooltip content={<Tip fmt={(v) => v.toFixed(0)} />} />
                <Line dataKey="ROAS" stroke={C.red} strokeWidth={3} dot={false} isAnimationActive={false} />
                <Line dataKey="CTR" stroke={C.gold} strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line dataKey="CPC" stroke={C.blue} strokeWidth={2} dot={false} isAnimationActive={false} />
                <Line dataKey="Conversion" stroke={C.muted} strokeWidth={1.5} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
            <div className="row wrap small" style={{ gap: 14 }}>{[['ROAS', C.red], ['CTR', C.gold], ['CPC', C.blue], ['Conversion', C.muted]].map(([n, c]) => <span key={n} className="row" style={{ gap: 6 }}><i className="dot" style={{ background: c }} />{n} (index, baseline 100)</span>)}</div>
          </div>
          <div className="card stack">
            <div className="row between"><span className="pill violet">{a.kind.replace(/_/g, ' ')}</span><Ring value={a.confidence} /></div>
            <Block c={C.red} l="What happened">{a.what_happened}</Block>
            <Block c={C.gold} l="Probable cause">{a.probable_cause}</Block>
            <Block c={C.blue} l="Recommended action">{a.recommended_action}</Block>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="stack stagger">
          <div className="card rec top">
            <div className="row between wrap"><span className="pill gold">Budget Decision Engine</span><span className="muted">confidence <b className="num" style={{ color: 'var(--text)' }}>{pct(r.confidence)}</b></span></div>
            <div className="big">Move {inr(r.amount)}/day</div>
            <div className="flow"><div className="node"><small>From</small>{r.source_name}</div><div className="arrow">→</div><div className="node"><small>To</small>{r.target_name}</div>
              <div className="node" style={{ flex: '0 0 auto' }}><small>Expected incremental profit</small><b className="up num" style={{ fontSize: 22 }}>{plus(r.expected_profit)}/day</b></div></div>
            <ul className="why">{r.why.map((x, i) => <li key={i}>{x}</li>)}</ul>
            <div className="stack" style={{ gap: 8 }}>
              {r.policy_drivers.slice(0, 3).map((x) => (
                <div className="driver" key={x.dim}><span>{x.label} <span className="muted">({pct(x.weight)})</span></span>
                  <div className="bar"><i style={{ width: '100%', transform: `scaleX(${Math.max(0.02, x.share)})`, background: x.value >= 0 ? C.teal : C.red }} /></div>
                  <span className={'num ' + (x.value >= 0 ? 'up' : 'down')} style={{ textAlign: 'right' }}>{plus(x.value)}</span></div>
              ))}
            </div>
            <div className="row wrap" style={{ gap: 16 }}>{r.guardrails.map((g) => <span className="check" key={g.label}><i className={'dot' + (g.ok ? '' : ' bad')} />{g.label}: <b className="num">{g.value}</b></span>)}</div>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="stack stagger">
          <div className="banner changed">
            <div className="row" style={{ marginBottom: 6 }}><span className="pill gold">Scenario</span><b>Supplier delay: only {w.stock_units} Silk Scarves left (cover {w.target_cover_before.toFixed(0)} d → {w.target_cover_after.toFixed(1)} d)</b></div>
            {w.narrative}
          </div>
          <div className="grid g2">
            <div className="card"><h3>Before the inventory change</h3><div style={{ fontWeight: 650, fontSize: 16 }}>{w.top_before.title}</div><b className="up num" style={{ fontSize: 22 }}>{plus(w.top_before.expected_profit)}/day</b></div>
            <div className="card" style={{ borderColor: 'var(--gold)' }}><h3>After — decision re-solved</h3><div style={{ fontWeight: 650, fontSize: 16 }}>{w.top_after.title}</div><b className="gold num" style={{ fontSize: 22 }}>{plus(w.top_after.expected_profit)}/day</b></div>
          </div>
          <div className="row"><button className="btn teal" onClick={() => { setCompany('fashion'); go('whatif', null, { sku: data.target_sku, on_hand: w.stock_units }) }}>Open in simulator and play with it →</button></div>
        </div>
      )}

      {step === 4 && (
        <div className="grid g2 stagger">
          <div className="card stack">
            <h3>5 · Close the loop</h3>
            <p>Approve the decision. The system simulates what the world did, compares it to its own prediction, and recalibrates.</p>
            <div className="card" style={{ background: 'var(--card2)' }}><div className="muted small">Decision</div><b>{r.title}</b></div>
            {!outcome ? <button className="btn primary" disabled={busy} onClick={approve}>Approve &amp; simulate outcome</button> : <span className="pill teal">✓ Approved &amp; scored</span>}
          </div>
          <div className="card stack">
            <h3>prediction → action → actual → error → confidence</h3>
            {outcome ? (
              <>
                <Row l="Predicted" v={plus(outcome.predicted_profit) + '/day'} /><Row l="Action" v="Approved" /><Row l="Actual outcome" v={plus(outcome.actual_profit) + '/day'} tone="up" />
                <Row l="Error" v={(outcome.error_pct * 100).toFixed(1) + '%  (' + plus(outcome.error) + ')'} tone={outcome.error < 0 ? 'down' : 'up'} />
                <Row l="Confidence" v={`${pct(outcome.confidence_before)} → ${pct(outcome.confidence_after)}`} tone="gold" />
                <Row l="Type calibration" v={`${pct(outcome.calibration_accuracy)} accuracy · n=${outcome.calibration_n}`} />
                <div className="muted small">Future “{outcome.rec_type.replace(/_/g, ' ')}” recommendations now inherit this calibration.</div>
                <button className="btn ghost" onClick={() => { setCompany('fashion'); go('history') }}>See decision history →</button>
              </>
            ) : <div className="muted">Approve to see the outcome.</div>}
          </div>
        </div>
      )}

      <div className="row between">
        <button className="btn ghost" disabled={step === 0} onClick={() => setStep((s) => Math.max(0, s - 1))}>← Back</button>
        {step < 4 ? <button className="btn primary" onClick={next}>Next: {STEPS[step + 1]} →</button> : <button className="btn ghost" onClick={() => { setCompany('startup'); go('optimizer') }}>Try another company’s policy →</button>}
      </div>
    </div>
  )
}

const Mini = ({ l, v, tone }) => <div><div className="muted small">{l}</div><div className={'num ' + (tone || '')} style={{ fontSize: 20, fontWeight: 700 }}>{v}</div></div>
const Block = ({ c, l, children }) => <div><div className="small" style={{ fontWeight: 700, color: c, textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 3 }}>{l}</div>{children}</div>
const Row = ({ l, v, tone }) => <div className="row between" style={{ borderBottom: '1px solid var(--line)', paddingBottom: 8 }}><span className="muted">{l}</span><b className={'num ' + (tone || '')}>{v}</b></div>
