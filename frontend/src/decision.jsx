import { useState } from 'react'
import { inr, pct, plus } from './api'
import Icon from './icons'
import { fx, nameOf } from './lib'
import { SectionLabel } from './editorial'
import { Tag } from './provenance'
import { Bars, Drawer, Health, Hint, Metric, Section } from './ui'

const ACTION = { increase: 'Increase', decrease: 'Decrease', hold: 'Hold', pause: 'Pause' }

/** The answer: where the next ₹1 goes. Everything else on the page is evidence for this. */
export function Verdict({ w, company, onReview, onOpen, hasRec, headline = false }) {
  if (!w) return <div className="card empty">No campaign clears this company’s guardrails right now.</div>
  const up = w.delta > 0
  const alt = w.alternatives?.[0]
  const Name = headline ? 'h3' : 'h2'
  const top = Math.max(w.profit_per_rupee, alt?.profit_per_rupee ?? 0, 0.01)
  return (
    <section className="verdict hero" aria-labelledby="verdict-h">
      <div className="verdict-main">
        <span className="wm" aria-hidden="true">{company}</span>
        <div className="eyebrow">Next ₹1 · {company}</div>
        {headline && <p className="mega" role="heading" aria-level={2}><span>Where</span><span>should the</span><span>next ₹1</span><span>go?</span></p>}
        <Name id="verdict-h" className="winner">{w.sku_name}<span> × {w.platform}</span></Name>
        <div className="muted camp">{w.campaign}</div>
        <div className="verdict-kpis">
          <div className="hero-num">
            <Hint k="ppr" align="left"><span className="eyebrow">Incremental profit / ₹1</span></Hint>
            <b className="num up">{fx(w.profit_per_rupee)}</b>
          </div>
          <div className="hero-num-2">
            <span className="eyebrow">Expected incremental profit</span>
            <b className="num up">{plus(w.recommended_profit)}<small>/day</small></b>
          </div>
        </div>
        <div className="verdict-sub">
          <div className="alloc">
            <Hint k="budget" align="left"><span className="eyebrow">Daily allocation</span></Hint>
            <div className="alloc-line num">
              <span className="muted">{inr(w.current)}</span><Icon name="arrow" size={14} className="muted" />
              <b>{inr(w.recommended)}</b>
              {w.delta !== 0 && <span className={up ? 'up' : 'down'}>{plus(w.delta)}</span>}
              {w.delta === 0 && <span className="muted">no change</span>}
            </div>
            <span className="muted small">{ACTION[w.action]}</span>
          </div>
          <div className="alloc">
            <Hint k="conf" align="left"><span className="eyebrow">Confidence</span></Hint>
            <b className="num" style={{ fontSize: 22 }}>{pct(w.confidence)}</b>
          </div>
        </div>
        {w.ml_conv_rate != null && (
          <p className="ml-chip small"><Tag kind="model" /> predicts {(w.ml_conv_rate * 100).toFixed(2)} purchases per 100 clicks (engine multiplier {w.ml_lift.toFixed(2)}×); the policy engine makes the call.</p>
        )}
        {w.policy_note && <p className="note small">{w.policy_note}</p>}
        <div className="row wrap" style={{ marginTop: 4 }}>
          {hasRec && <button className="btn primary" onClick={onReview}>Review &amp; approve action</button>}
          <button className="btn ghost" onClick={() => onOpen(w)}>Full analysis</button>
        </div>
      </div>
      <div className="verdict-why slab">
        <div className="eyebrow">Why this wins</div>
        <ul className="why">{w.why_won.map((t, i) => <li key={i}>{t}</li>)}</ul>
        {alt && (
          <div className="vs" aria-label="Strongest alternative">
            <div className="eyebrow">Strongest alternative</div>
            <div className="vs-row"><span>{w.sku_name}</span><i style={{ transform: `scaleX(${w.profit_per_rupee / top})` }} /><b className="num">{fx(w.profit_per_rupee)}</b></div>
            <div className="vs-row alt"><span>{alt.sku_name}</span><i style={{ transform: `scaleX(${Math.max(0, alt.profit_per_rupee) / top})` }} /><b className="num">{fx(alt.profit_per_rupee)}</b></div>
          </div>
        )}
      </div>
    </section>
  )
}

export function WhyNot({ alts, onOpen }) {
  if (!alts?.length) return null
  return (
    <section className="card whynot" aria-labelledby="whynot-h">
      <h3 id="whynot-h">Why not the others</h3>
      <div className="stack" style={{ gap: 2 }}>
        {alts.map((a) => (
          <button key={a.campaign_id} className="list-item alt" onClick={() => onOpen(a)}>
            <div className="row between"><b>{nameOf(a)}</b><span className="row small muted num">{fx(a.profit_per_rupee)} / ₹1 <Icon name="right" size={14} /></span></div>
            <ul className="lost">{a.why_lost.slice(0, 2).map((t, i) => <li key={i}>{t}</li>)}</ul>
          </button>
        ))}
      </div>
    </section>
  )
}

/** ROAS IS NOT THE DECISION: HIGH ROAS ≠ HIGH INCREMENTAL PROFIT, computed live from the engine. */
export function TrapCard({ trap, candidates }) {
  const { roas_leader: l, winner: w } = trap
  if (!l || !w) return null
  const alt = trap.active ? null : candidates.filter((x) => x.campaign_id !== w.campaign_id).sort((a, b) => b.roas - a.roas)[0]
  const rows = trap.active
    ? [['ROAS leader', l, false], ['Marginal-profit leader · wins the next ₹1', w, true]]
    : [['Next ₹1 winner · also ROAS leader', w, true], ...(alt ? [['Highest-ROAS alternative', alt, false]] : [])]
  const max = Math.max(...rows.map(([, x]) => x.roas))
  const pmax = Math.max(...rows.map(([, x]) => Math.abs(x.profit_per_rupee)), 0.01)
  return (
    <section className="card trapcard" aria-labelledby="trap-h">
      <SectionLabel>The ROAS trap</SectionLabel>
      <h3 id="trap-h" className="trap-title">ROAS is not<br />the decision.</h3>
      <p className="trap-claim">High ROAS ≠ high incremental profit</p>
      <div className="trap">
        {rows.map(([label, x, win]) => (
          <div className={'trap-row' + (win ? ' win' : '')} key={label}>
            <div className="trap-id"><small>{label}</small><b>{nameOf(x)}</b></div>
            <div className="trap-fig">
              <Hint k="roas" align="left"><span className="eyebrow">ROAS</span></Hint>
              <b className="num roas-fig">{x.roas.toFixed(1)}×</b>
              <span className="trapbar" aria-hidden="true"><i style={{ transform: `scaleX(${x.roas / max})` }} /></span>
            </div>
            <div className="trap-fig">
              <Hint k="ppr" align="left"><span className="eyebrow">Profit / ₹1</span></Hint>
              <b className={'num profit-fig ' + (x.profit_per_rupee < 0 ? 'down' : win ? 'up' : '')}>{fx(x.profit_per_rupee)}</b>
              <span className={'trapbar ' + (x.profit_per_rupee < 0 ? 'neg' : 'pos')} aria-hidden="true"><i style={{ transform: `scaleX(${Math.abs(x.profit_per_rupee) / pmax})` }} /></span>
            </div>
            <div className="trap-fig hide-sm">
              <span className="eyebrow">Incremental profit</span>
              <b className="num">{plus(x.step_profit)}</b>
              <span className="muted small">per ₹1,000 added</span>
            </div>
          </div>
        ))}
      </div>
      <p className="muted trap-msg">{trap.active ? trap.message : 'The engine ranks on marginal profit and policy value, not ROAS. A higher-ROAS campaign would lose the next ₹1 if it earned less per ₹1.'}</p>
    </section>
  )
}

function Row({ x, win, onOpen }) {
  const [open, setOpen] = useState(false)
  const id = 'row-' + x.campaign_id
  return (
    <>
      <tr className={'prow' + (win ? ' win' : '') + (!x.eligible ? ' gated' : '')}>
        <td className="rank num">{String(x.rank).padStart(2, '0')}</td>
        <td>
          <button className="row-btn" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}>
            <span><b>{x.sku_name}</b><span className="muted"> · {x.platform}</span><small>{x.campaign}</small></span>
            <Icon name="chevron" size={14} className={'caret' + (open ? ' open' : '')} />
          </button>
        </td>
        <td className="r hide-sm"><b className={'num ' + (x.eligible && x.recommended_profit > 0 ? 'up' : '')}>{x.eligible ? plus(x.recommended_profit) : '—'}</b></td>
        <td className="r"><b className={'num pr ' + (x.profit_per_rupee < 0 ? 'down' : x.eligible ? 'up' : '')}>{fx(x.profit_per_rupee)}</b></td>
        <td className="hide-sm">
          {x.eligible
            ? <span className={'act ' + x.action}>{ACTION[x.action]}{x.delta ? <span className="num"> {plus(x.delta)}</span> : null}</span>
            : <span className="act gated" title={x.gate_reason}>Gated</span>}
        </td>
        <td className="r"><button className="btn ghost small" onClick={() => onOpen(x)} aria-label={`Details for ${nameOf(x)}`}>Details</button></td>
      </tr>
      {open && (
        <tr className="prow-detail" id={id}>
          <td />
          <td colSpan={5}>
            <div className="metrics">
              <Metric k="roas" label="ROAS" value={x.roas.toFixed(2) + '×'} />
              <Metric k="mroas" label="Marginal ROAS" value={x.marginal_roas.toFixed(2) + '×'} />
              <Metric k="margin" label="Margin" value={pct(x.margin)} />
              <Metric k="cac" label="Marginal CAC" value={x.marginal_cac ? inr(x.marginal_cac) : '—'} />
              <Metric k="cvr" label="CVR" value={(x.cvr * 100).toFixed(1) + '%'} />
              <Metric k="inv" label="Inventory" value={Math.round(x.inventory_days) + ' d'} />
              <Metric k="risk" label="Stockout risk" value={pct(x.stockout_risk)} tone={x.stockout_risk > 0.3 ? 'down' : ''} />
              <Metric k="conf" label="Confidence" value={pct(x.confidence)} />
            </div>
            <div className="row" style={{ marginTop: 10 }}><Hint k="health" align="left"><span className="eyebrow">Campaign health</span></Hint><Health h={x.health} /></div>
            {!x.eligible && <p className="small down" style={{ marginTop: 8 }}>Gated: {x.gate_reason}</p>}
          </td>
        </tr>
      )}
    </>
  )
}

export function Portfolio({ rows, winnerId, onOpen }) {
  const [all, setAll] = useState(false)
  const shown = all ? rows : rows.slice(0, 8)
  return (
    <section className="portfolio" aria-labelledby="pf-h">
      <div className="row between wrap pf-head">
        <div><SectionLabel>Portfolio ranking</SectionLabel><h3 id="pf-h" className="pf-title">Product × campaign × platform</h3></div>
        <span className="muted small">{rows.length} candidates · ranked by policy-weighted value per ₹1</span>
      </div>
      <div className="tscroll" tabIndex={0} role="region" aria-label="Opportunity ranking table, scrollable">
        <table className="table ptable">
          <thead><tr><th style={{ width: 64 }}>Rank</th><th>Product · campaign</th><th className="r hide-sm">Expected incremental profit</th><th className="r"><Hint k="ppr" align="right"><span>Profit / ₹1</span></Hint></th><th className="hide-sm">Action</th><th /></tr></thead>
          <tbody>{shown.map((x) => <Row key={x.campaign_id} x={x} win={x.campaign_id === winnerId} onOpen={onOpen} />)}</tbody>
        </table>
      </div>
      {rows.length > 8 && <button className="btn ghost small" style={{ marginTop: 10 }} onClick={() => setAll(!all)}>{all ? 'Show top 8' : `Show all ${rows.length}`}</button>}
    </section>
  )
}

/** Tertiary layer: evidence, health contributors, calculation. */
export function CandidateDrawer({ x, winner, onClose }) {
  if (!x) return null
  const isWin = winner && x.campaign_id === winner.campaign_id
  return (
    <Drawer open onClose={onClose} title={nameOf(x)} kicker={`#${x.rank} · ${x.campaign}`}>
      <div className="row wrap" style={{ marginBottom: 12 }}>
        <Health h={x.health} />
        {isWin && <span className="pill gold">Next ₹1 winner</span>}
        {!x.eligible && <span className="pill red">Gated</span>}
      </div>
      {!x.eligible && <p className="down">{x.gate_reason}</p>}
      <Section title={isWin ? 'Why it won' : 'Why it ranks lower'}>
        <ul className="why">{(isWin ? winner.why_won : x.why_lost || []).map((t, i) => <li key={i}>{t}</li>)}</ul>
      </Section>
      <Section title="Marginal economics">
        <div className="metrics">
          <Metric k="ppr" label="Profit / ₹1" value={fx(x.profit_per_rupee)} />
          <Metric k="value" label="Policy value / ₹1" value={x.policy_value_per_rupee.toFixed(2)} />
          <Metric k="roas" label="ROAS" value={x.roas.toFixed(2) + '×'} />
          <Metric k="mroas" label="Marginal ROAS" value={x.marginal_roas.toFixed(2) + '×'} />
          <Metric k="margin" label="Margin" value={pct(x.margin)} />
          <Metric k="cac" label="Marginal CAC" value={x.marginal_cac ? inr(x.marginal_cac) : '—'} />
          <Metric k="cvr" label="CVR" value={(x.cvr * 100).toFixed(1) + '%'} />
          <Metric k="inv" label="Inventory" value={Math.round(x.inventory_days) + ' d'} />
        </div>
        <p className="calc num">{x.marginal_roas.toFixed(2)} marginal ROAS × {pct(x.margin)} margin − ₹1 = <b>{fx(x.profit_per_rupee)}</b> per ₹1</p>
      </Section>
      <Section title="Campaign health">
        <Bars items={x.health.parts} />
      </Section>
      <Section title="Allocation">
        <div className="alloc-line num"><span className="muted">{inr(x.current)}</span><Icon name="arrow" size={14} /><b>{inr(x.recommended)}</b>{x.delta !== 0 && <span className={x.delta > 0 ? 'up' : 'down'}>{plus(x.delta)}</span>}</div>
        <p className="muted small">{ACTION[x.action]} · expected {plus(x.recommended_profit)}/day · creative {x.creative_age} days old{x.anomaly ? ` · ${x.anomaly.replace(/_/g, ' ')}` : ''}</p>
      </Section>
    </Drawer>
  )
}

/** Winner summary used by the simulator and the guided demo. `other` adds a delta vs a baseline winner. */
export function WinnerCard({ label, w, tone, other }) {
  if (!w) return <div className="card wcard"><div className="eyebrow">{label}</div><p className="muted">No campaign clears the guardrails.</p></div>
  const d = other ? w.profit_per_rupee - other.profit_per_rupee : 0
  return (
    <div className={'card wcard ' + (tone || '')}>
      <div className="eyebrow">{label}</div>
      <h3 className="wname">{w.sku_name}<span> × {w.platform}</span></h3>
      <div className="muted small">{w.campaign}</div>
      <div className="wnum">
        <Hint k="ppr" align="left"><span className="eyebrow">Profit / ₹1</span></Hint>
        <b className="num up">{fx(w.profit_per_rupee)}</b>
        {other && Math.abs(d) >= 0.005 && <span className={'num small ' + (d > 0 ? 'up' : 'down')}>{d > 0 ? '+' : '−'}{fx(Math.abs(d))} vs baseline</span>}
      </div>
      <div className="wmeta small">
        <span><span className="muted">Allocation</span> <b className="num">{inr(w.current)} → {inr(w.recommended)}</b></span>
        <span><span className="muted">Expected</span> <b className="num up">{plus(w.recommended_profit)}/day</b></span>
        <span><Hint k="conf" align="left"><span className="muted">Confidence</span></Hint> <b className="num">{pct(w.confidence)}</b></span>
      </div>
    </div>
  )
}
