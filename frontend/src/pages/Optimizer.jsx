import { useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { compact, inr, pct, plus, useApi } from '../api'
import { Loading, RecCard, Tip } from '../components'
import { CandidateDrawer } from '../decision'
import ProductArt from '../ProductArt'
import Icon from '../icons'
import { C, axis, fx, nameOf, shortName } from '../lib'
import { Disclosure, Health, Hint, Metric } from '../ui'

const ACTION = { increase: 'Increase', decrease: 'Decrease', hold: 'Hold', pause: 'Pause' }

export default function Optimizer({ company }) {
  const { data, error, reload } = useApi('/plan', { company_id: company })
  const [sel, setSel] = useState(null)
  const cmap = useMemo(() => Object.fromEntries((data?.candidates ?? []).map((c) => [c.campaign_id, c])), [data])
  if (!data) return <div className="page"><Loading error={error} /></div>
  const t = data.totals, w = data.next_rupee
  const runner = w?.alternatives?.[0]
  const moves = data.recommendations
  const topMove = moves.find((m) => m.rec_type === 'move_budget')
  const chart = data.allocation.map((a) => ({ name: shortName(a.name), Current: a.current, Recommended: a.recommended }))
  return (
    <div className="page">
      <section className="verdict hero cap" aria-labelledby="opt-h">
        <div className="verdict-main">
          <span className="wm" aria-hidden="true">{data.company_name}</span>
          <div className="eyebrow">Decision workspace · {data.policy.name} policy</div>
          <p className="mega" role="heading" aria-level={2}><span>Capital</span><span>allocation</span></p>
          {w ? (
            <>
              <h3 id="opt-h" className="winner">{w.sku_name}<span> × {w.platform}</span></h3>
              <div className="muted camp">Wins the next marginal ₹1 · {w.campaign}</div>
            </>
          ) : <h3 id="opt-h" className="winner">No move clears the guardrails</h3>}
          {w && (
            <div className="capline" aria-label="Current, recommended and move">
              <div><span className="eyebrow">Current</span><b className="num">{inr(w.current)}</b></div>
              <Icon name="arrow" size={28} className="capline-arrow" />
              <div><span className="eyebrow">Recommended</span><b className="num">{inr(w.recommended)}</b></div>
              <div><span className="eyebrow">Move</span><b className={'num ' + (w.delta > 0 ? 'up' : w.delta < 0 ? 'down' : '')}>{w.delta ? plus(w.delta) : '—'}</b></div>
            </div>
          )}
          {topMove && (
            <div className="fromto">
              <div><span className="eyebrow">From</span><b>{topMove.source_name}</b></div>
              <Icon name="arrow" size={22} className="muted" />
              <div><span className="eyebrow">To</span><b>{topMove.target_name}</b></div>
            </div>
          )}
          <div className="verdict-kpis">
            <div className="hero-num">
              <Hint k="ppr" align="left"><span className="eyebrow">Plan incremental profit</span></Hint>
              <b className="num up">{plus(t.incremental_profit)}<small>/day</small></b>
              <span className="muted small">≈ {compact(t.incremental_profit_30d)} / 30 days · {inr(t.moved)} moved ({pct(t.moved / t.budget_before)}) · total spend unchanged</span>
            </div>
            {w && (
              <div className="hero-num-2">
                <span className="eyebrow">Profit / ₹1</span>
                <b className="num up">{fx(w.profit_per_rupee)}</b>
              </div>
            )}
          </div>
        </div>
        <div className="poster"><ProductArt key={company} companyId={company} brand={data.company_name} /></div>
      </section>
      {w && (
        <section className="whyrow" aria-label="Why it won and why the alternative lost">
          <div>
            <div className="eyebrow">Why it won</div>
            <ul className="why">{w.why_won.slice(0, 3).map((x, i) => <li key={i}>{x}</li>)}</ul>
          </div>
          {runner && (
            <div>
              <div className="eyebrow">Why {nameOf(runner)} lost</div>
              <ul className="lost">{runner.why_lost.slice(0, 2).map((x, i) => <li key={i}>{x}</li>)}</ul>
              <button className="link-btn" onClick={() => setSel(runner)}>Compare in detail</button>
            </div>
          )}
        </section>
      )}

      <section aria-labelledby="moves-h">
        <div className="row between wrap" style={{ marginBottom: 10 }}>
          <h3 id="moves-h" className="sec-h">Where budget moves</h3>
          <span className="muted small">{moves.length} actions · ranked by expected incremental profit</span>
        </div>
        <Moves moves={moves} reload={reload} />
      </section>

      <section className="card" aria-labelledby="alloc-h">
        <h3 id="alloc-h">Allocation by campaign</h3>
        <div className="tscroll" tabIndex={0} role="region" aria-label="Allocation by campaign, scrollable">
          <table className="table ptable">
            <thead><tr><th>Campaign</th><th className="r">Daily budget</th><th className="r"><Hint k="ppr" align="right"><span>Profit / ₹1</span></Hint></th><th className="hide-sm">Action</th><th className="hide-sm"><Hint k="health"><span>Health</span></Hint></th><th /></tr></thead>
            <tbody>{data.allocation.map((a) => <AllocRow key={a.campaign_id} a={a} x={cmap[a.campaign_id]} win={w?.campaign_id === a.campaign_id} onOpen={setSel} />)}</tbody>
          </table>
        </div>
        <Disclosure title="Current vs recommended chart" summary="same data as the table above">
          <div role="img" aria-label="Bar chart of current and recommended daily budget per campaign. The same values are in the allocation table above.">
            <ResponsiveContainer width="100%" height={Math.max(300, chart.length * 32)}>
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
        </Disclosure>
      </section>
      <CandidateDrawer x={sel} winner={w} onClose={() => setSel(null)} />
    </div>
  )
}

function Moves({ moves, reload }) {
  const [all, setAll] = useState(false)
  if (!moves.length) return <div className="card empty">No move clears the guardrails under this policy.</div>
  const shown = all ? moves : moves.slice(0, 3)
  return (
    <>
      <div className="stack">{shown.map((r, i) => <RecCard key={r.rec_id} rec={r} top={i === 0} onDecided={reload} expanded={false} />)}</div>
      {moves.length > 3 && <button className="btn ghost small" style={{ marginTop: 10 }} onClick={() => setAll(!all)}>{all ? 'Show top 3' : `Show all ${moves.length} actions`}</button>}
    </>
  )
}

function AllocRow({ a, x, win, onOpen }) {
  const [open, setOpen] = useState(false)
  const id = 'alloc-' + a.campaign_id
  return (
    <>
      <tr className={'prow' + (win ? ' win' : '') + (!a.eligible ? ' gated' : '')}>
        <td>
          <button className="row-btn" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}>
            <Icon name="chevron" size={14} className={'caret' + (open ? ' open' : '')} />
            <span><b>{a.sku_name}</b><span className="muted"> · {a.platform}</span><small>{a.name}</small></span>
          </button>
        </td>
        <td className="r num">
          <span className="muted">{inr(a.current)}</span> → <b>{inr(a.recommended)}</b>
          {a.delta !== 0 && <small className={a.delta > 0 ? 'up' : 'down'} style={{ display: 'block' }}>{plus(a.delta)}</small>}
        </td>
        <td className="r"><b className={'num ' + (a.marginal_profit_per_rupee < 0 ? 'down' : a.eligible ? 'up' : '')}>{fx(a.marginal_profit_per_rupee)}</b></td>
        <td className="hide-sm"><span className={'act ' + (a.eligible || a.action === 'pause' ? a.action : 'gated')}>{!a.eligible && a.action !== 'pause' ? 'Gated' : ACTION[a.action]}</span></td>
        <td className="hide-sm">{x && <Health h={x.health} />}</td>
        <td className="r">{x && <button className="btn ghost small" onClick={() => onOpen(x)} aria-label={`Details for ${nameOf(a)}`}>Details</button>}</td>
      </tr>
      {open && (
        <tr className="prow-detail" id={id}>
          <td colSpan={6}>
            <div className="metrics">
              <Metric k="roas" label="ROAS" value={a.roas.toFixed(2) + '×'} />
              <Metric k="mroas" label="Marginal ROAS" value={a.marginal_roas.toFixed(2) + '×'} />
              {x && <Metric k="margin" label="Margin" value={pct(x.margin)} />}
              {x && <Metric k="cac" label="Marginal CAC" value={x.marginal_cac ? inr(x.marginal_cac) : '—'} />}
              {x && <Metric k="cvr" label="CVR" value={(x.cvr * 100).toFixed(1) + '%'} />}
              {x && <Metric k="inv" label="Inventory" value={Math.round(x.inventory_days) + ' d'} />}
              {x && <Metric k="conf" label="Confidence" value={pct(x.confidence)} />}
              <Metric text="Share of the best opportunity’s policy-weighted value per ₹1." label="Opportunity" value={a.opportunity_score} />
            </div>
            {!a.eligible && x?.gate_reason && <p className="small down" style={{ marginTop: 8 }}>Gated: {x.gate_reason}</p>}
          </td>
        </tr>
      )}
    </>
  )
}
