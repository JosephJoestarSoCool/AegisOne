import { useState } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { inr, pct, plus, post, useApi } from '../api'
import { Ring, RecCard, Tip, ErrorState } from '../components'
import { CandidateDrawer, TrapCard, Verdict, WhyNot, WinnerCard } from '../decision'
import Icon from '../icons'
import { C, axis, fx, nameOf } from '../lib'
import { Disclosure, Metric } from '../ui'

const STEPS = ['Data', 'Diagnose', 'Compare', 'Decide', 'Simulate', 'Approve', 'Learn']
const PHASES = ['Reconcile platform data against the sales ledger', 'Diagnose anomalies and their causes', 'Rank every product × campaign × platform', 'Solve the budget and re-run the what-if']

function DemoLoading({ error }) {
  if (error) return <ErrorState error={error} what="the demo analysis" />
  return (
    <div className="card demo-load" role="status" aria-label="Loading">
      <div className="eyebrow">Running the full analysis on the backend</div>
      <ol>{PHASES.map((p) => <li key={p}><i aria-hidden="true" />{p}</li>)}</ol>
    </div>
  )
}

export default function Demo({ go, setCompany, companies }) {
  const { data, error, reload } = useApi('/demo')
  const [step, setStep] = useState(0)
  const [outcome, setOutcome] = useState(null)
  const [busy, setBusy] = useState(false)
  const [sel, setSel] = useState(null)
  if (!data) return <div className="page"><DemoLoading error={error} /></div>
  const cname = companies?.find((c) => c.company_id === data.company_id)?.name ?? data.company_id
  const d1 = data.step1_data, a = data.step2_diagnosis, cmp = data.step_compare, r = data.step3_decision, w = data.step4_whatif
  const rc = d1.reconciliation, camp = d1.campaign
  const win = cmp.next_rupee
  const ser = d1.series
  const base = ser.slice(0, 25)
  const mean = (k) => base.reduce((s, x) => s + x[k], 0) / base.length
  const idx = ser.map((x) => ({ date: x.date, ROAS: (x.roas / mean('roas')) * 100, CTR: (x.ctr / mean('ctr')) * 100, CPC: (x.cpc / mean('cpc')) * 100, Conversion: (x.cvr / mean('cvr')) * 100 }))
  const approve = async () => {
    setBusy(true)
    try { setOutcome(await post('/recommendations/decide', { recommendation: r, approve: true })); setStep(6) } finally { setBusy(false) }
  }
  const resetAll = async () => { await post('/reset', {}); setOutcome(null); setStep(0); setSel(null); reload() }
  const roasDrop = ((camp.roas / mean('roas') - 1) * 100)
  const tgtName = cmp.candidates.find((c) => c.sku_id === data.target_sku)?.sku_name ?? 'the winner'
  const errPct = outcome ? outcome.error_pct : null
  const HEAD = [
    [`Platforms over-claim orders by ${pct(rc.overcount_pct)}.`, 'Every number downstream uses reconciled orders, not the platform’s claim.'],
    [`${camp.name} is losing efficiency: ROAS ${roasDrop.toFixed(0)}% vs its own baseline.`, 'The engine reads the signals and names the cause, with a confidence.'],
    [`${tgtName} has the better marginal return.`, `${cmp.candidates.length} product × campaign options compete for the next ₹1, ranked on incremental profit per ₹1 and policy, not ROAS.`],
    [`Shift ${inr(r.amount)}/day.`, 'Sized by the optimizer inside every guardrail.'],
    [`Supplier delay: only ${w.stock_units} units of ${tgtName} left.`, 'Change the business and the decision re-solves.'],
    ['Approve, and the system measures what happened.', 'No hard-coded answers: the outcome is simulated and scored.'],
    [errPct == null ? 'The model compares prediction to reality.' : `The model was ${Math.abs(errPct * 100).toFixed(0)}% too ${errPct < 0 ? 'optimistic' : 'conservative'}.`, 'It recalibrates: future recommendations of this type inherit the learned accuracy.'],
  ]
  return (
    <div className="page">
      <div className="row between wrap">
        <div>
          <div className="eyebrow">Guided demo · {cname} · deterministic</div>
          <h2 className="demo-h">{HEAD[step][0]}</h2>
          <div className="muted">{HEAD[step][1]}</div>
        </div>
        <button className="btn ghost" onClick={resetAll} title="Regenerate data and clear learned feedback">Reset demo</button>
      </div>

      <nav aria-label="Demo steps"><ol className="story">
        {STEPS.map((s, i) => (
          <li key={s}><button aria-current={i === step ? 'step' : undefined} className={i < step ? 'done' : ''} onClick={() => setStep(i)}>
            <i aria-hidden="true">{i < step ? <Icon name="check" size={12} /> : i + 1}</i>{s}
          </button></li>
        ))}
      </ol></nav>

      <div key={step} className="stage">
        {step === 0 && (
          <div className="grid g-5-7">
            <div className="card">
              <h3>ROAS · reported vs reconciled</h3>
              <div className="cmp-roas">
                <div><span className="muted small">Platforms report</span><b className="num down">{rc.reported_roas.toFixed(2)}×</b></div>
                <Icon name="arrow" size={20} className="muted" />
                <div><span className="muted small">Sales ledger says</span><b className="num gold">{rc.reconciled_roas.toFixed(2)}×</b></div>
              </div>
              <p className="muted small" style={{ margin: '12px 0 0' }}>Platforms count the same sale more than once. Reconciling against the ledger removes that overcount.</p>
            </div>
            <div className="card stack">
              <h3>Unified business data</h3>
              <div className="metrics">
                <Metric text="Ad platforms connected." label="Platforms" value={rc.platforms} />
                <Metric text="Campaigns across all platforms." label="Campaigns" value={rc.campaigns} />
                <Metric text="Products with price, cost and stock." label="SKUs" value={rc.skus} />
                <Metric text="One row per campaign-day." label="Daily ad rows" value={rc.rows.toLocaleString('en-IN')} />
              </div>
              <Disclosure title={`Campaign under watch · ${camp.name}`} summary="ROAS, CAC, margin and more">
                <div className="metrics">
                  <Metric k="roas" label="ROAS now" value={camp.roas.toFixed(2) + '×'} tone="down" />
                  <Metric k="cac" label="CAC" value={inr(camp.cac)} />
                  <Metric k="margin" label="Margin" value={pct(camp.margin)} />
                  <Metric text="Click-through rate." label="CTR" value={pct(camp.ctr, 2)} />
                  <Metric text="Cost per click." label="CPC" value={inr(camp.cpc, 1)} />
                  <Metric k="cvr" label="Conversion" value={pct(camp.cvr, 2)} />
                  <Metric k="budget" label="Daily budget" value={inr(camp.b0)} />
                  <Metric text="Days since the creative launched." label="Creative age" value={camp.creative_age + ' d'} />
                  <Metric k="mroas" label="Marginal ROAS" value={camp.marginal_roas.toFixed(2) + '×'} tone="down" />
                </div>
              </Disclosure>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="grid g-7-5">
            <div className="card">
              <h3>Signal trace · indexed to 25-day baseline = 100</h3>
              <div role="img" aria-label="Line chart of ROAS, CTR, CPC and conversion indexed to the 25-day baseline. ROAS and CTR fall sharply near the end while CPC rises. The values are in the table below.">
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
              </div>
              <div className="row wrap small" style={{ gap: 14 }}>{[['ROAS', C.red], ['CTR', C.gold], ['CPC', C.blue], ['Conversion', C.muted]].map(([n, c]) => <span key={n} className="row" style={{ gap: 6 }}><i className="dot" style={{ background: c }} />{n}</span>)}</div>
              <Disclosure title="Chart data" summary="weekly index values">
                <div className="tscroll" tabIndex={0} role="region" aria-label="Signal index values, scrollable">
                  <table className="table">
                    <thead><tr><th>Date</th><th className="r">ROAS</th><th className="r">CTR</th><th className="r">CPC</th><th className="r">Conversion</th></tr></thead>
                    <tbody>{idx.filter((_, i) => i % 5 === 0 || i === idx.length - 1).map((x) => <tr key={x.date}><td>{x.date}</td><td className="r num">{x.ROAS.toFixed(0)}</td><td className="r num">{x.CTR.toFixed(0)}</td><td className="r num">{x.CPC.toFixed(0)}</td><td className="r num">{x.Conversion.toFixed(0)}</td></tr>)}</tbody>
                  </table>
                </div>
              </Disclosure>
            </div>
            <div className="card stack">
              <div className="row between"><span className="pill violet">{a.kind.replace(/_/g, ' ')}</span><span className="row"><span className="muted small">confidence</span><Ring value={a.confidence} /></span></div>
              <Block c={C.red} l="What happened">{a.what_happened}</Block>
              <Block c={C.gold} l="Probable cause">{a.probable_cause}</Block>
              <Block c={C.blue} l="Recommended action">{a.recommended_action}</Block>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="stack">
            <Verdict w={win} company={cname} hasRec={false} onOpen={setSel} />
            <div className="grid g-7-5"><WhyNot alts={win?.alternatives} onOpen={setSel} /><TrapCard trap={cmp.roas_trap} candidates={cmp.candidates} /></div>
          </div>
        )}

        {step === 3 && <RecCard rec={r} top expanded={false} actions={false} />}

        {step === 4 && (
          <div className="stack">
            <div className="banner changed">
              <div className="row" style={{ marginBottom: 6 }}><span className="pill gold">Scenario</span><b>Supplier delay · cover {w.target_cover_before.toFixed(0)} d → {w.target_cover_after.toFixed(1)} d</b></div>
              {w.narrative}
            </div>
            <section className="cmp" aria-label="Next ₹1 before and after the supplier delay">
              <WinnerCard label="Before" w={w.next_rupee.before} />
              <Icon name="arrow" size={22} className="cmp-arrow" />
              <WinnerCard label="After · re-solved" w={w.next_rupee.after} tone="changed" other={w.next_rupee.before} />
            </section>
            <div className="row"><button className="btn teal" onClick={() => { setCompany(data.company_id); go('whatif', null, { sku: data.target_sku, on_hand: w.stock_units }) }}>Open in the simulator <Icon name="right" size={14} /></button></div>
          </div>
        )}

        {step === 5 && (
          <div className="grid g2">
            <div className="card stack">
              <h3>Decision to approve</h3>
              <b style={{ fontSize: 16, lineHeight: 1.35 }}>{r.title}</b>
              <div className="row wrap small">
                <span className="muted">Expected</span><b className="num up">{plus(r.expected_profit)}/day</b>
                <span className="muted">Confidence</span><b className="num">{pct(r.confidence)}</b>
              </div>
              {!outcome
                ? <button className="btn primary" disabled={busy} onClick={approve}>Approve &amp; simulate outcome</button>
                : <span className="pill teal"><Icon name="check" size={12} /> Approved &amp; scored</span>}
            </div>
            <div className="card">
              <h3>What approval does</h3>
              <ol className="steps-list">
                <li>Executes the budget move in the model.</li>
                <li>Simulates what the market did, with noise.</li>
                <li>Scores the prediction and updates confidence.</li>
              </ol>
            </div>
          </div>
        )}

        {step === 6 && (
          <div className="stack">
            {outcome ? (
              <div className="card">
                <h3>prediction → actual → error → confidence</h3>
                <div className="outcome">
                  <Out l="Predicted" v={plus(outcome.predicted_profit) + '/day'} />
                  <Out l="Actual" v={plus(outcome.actual_profit) + '/day'} tone="up" />
                  <Out l="Error" v={(outcome.error_pct * 100).toFixed(1) + '%'} tone={outcome.error < 0 ? 'down' : 'up'} />
                  <Out l="Confidence" v={`${pct(outcome.confidence_before)} → ${pct(outcome.confidence_after)}`} tone="gold" />
                </div>
                <p className="muted small" style={{ marginBottom: 0 }}>“{outcome.rec_type.replace(/_/g, ' ')}” accuracy is now {pct(outcome.calibration_accuracy)} over {outcome.calibration_n} decisions; future recommendations inherit it.</p>
              </div>
            ) : (
              <div className="card empty">Approve the decision first to see what the system learns. <button className="link-btn" onClick={() => setStep(5)}>Go to Approve</button></div>
            )}
            <section className="card final" aria-labelledby="final-h">
              <div className="eyebrow">Where should the next ₹1 go?</div>
              <h2 id="final-h" className="winner">{win.sku_name}<span> × {win.platform}</span></h2>
              <div className="row wrap" style={{ gap: 24 }}>
                <span><span className="muted small">Profit / ₹1</span> <b className="num up" style={{ fontSize: 22 }}>{fx(win.profit_per_rupee)}</b></span>
                <span><span className="muted small">Confidence</span> <b className="num" style={{ fontSize: 22 }}>{pct(win.confidence)}</b></span>
                {w.next_rupee.changed && <span className="muted small">If the supplier delay hits: <b style={{ color: 'var(--text)' }}>{nameOf(w.next_rupee.after)}</b> at {fx(w.next_rupee.after.profit_per_rupee)}</span>}
              </div>
              <div className="row wrap">
                <button className="btn ghost" onClick={() => { setCompany(data.company_id); go('history') }}>See decision history <Icon name="right" size={14} /></button>
                <button className="btn ghost" onClick={() => { setCompany(companies?.find((c) => c.company_id !== data.company_id)?.company_id ?? data.company_id); go('command') }}>Try another brand <Icon name="right" size={14} /></button>
              </div>
            </section>
          </div>
        )}
      </div>

      <div className="row between">
        <button className="btn ghost" disabled={step === 0} onClick={() => setStep((s) => Math.max(0, s - 1))}><Icon name="right" size={14} style={{ transform: 'rotate(180deg)' }} /> Back</button>
        {step < 6 && step !== 5 && <button className="btn primary" onClick={() => setStep((s) => s + 1)}>Next: {STEPS[step + 1]} <Icon name="right" size={14} /></button>}
        {step === 5 && outcome && <button className="btn primary" onClick={() => setStep(6)}>Next: Learn <Icon name="right" size={14} /></button>}
      </div>
      <CandidateDrawer x={sel} winner={win} onClose={() => setSel(null)} />
    </div>
  )
}

const Block = ({ c, l, children }) => <div><div className="small" style={{ fontWeight: 700, color: c, textTransform: 'uppercase', letterSpacing: '.05em', marginBottom: 3 }}>{l}</div>{children}</div>
const Out = ({ l, v, tone }) => <div><span className="muted small">{l}</span><b className={'num ' + (tone || '')}>{v}</b></div>
