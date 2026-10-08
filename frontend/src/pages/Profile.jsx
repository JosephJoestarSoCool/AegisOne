import { inr, pct, useApi } from '../api'
import { Loading } from '../components'
import { DIM_NOTE } from '../lib'
import { Disclosure, Hint } from '../ui'

const DIMS = [['profitability', 'Profitability'], ['growth', 'Growth'], ['revenue', 'Revenue'], ['inventory', 'Inventory'], ['cac', 'CAC efficiency'], ['risk', 'Risk control']]
const ORDER = ['nike', 'samsung', 'lenovo', 'lv', 'supreme']
const SOFT = '#fecaca', GOOD = '#a7f3d0'

function heat(v, current) {
  if (v === 0) return { bg: 'transparent', fg: 'var(--muted)', t: '—' }
  if (v <= -current + 1) return { bg: 'rgba(248,113,113,.28)', fg: SOFT, t: 'PAUSE' }
  const a = Math.min(0.32, 0.08 + Math.abs(v) / 40000)
  return v > 0 ? { bg: `rgba(45,212,191,${a})`, fg: GOOD, t: '+' + inr(v) } : { bg: `rgba(248,113,113,${a})`, fg: SOFT, t: inr(v) }
}

/** One plain-English line about what this brand optimises for, derived from its weights. */
function objective(weights) {
  const ranked = DIMS.map(([k, l]) => [l, weights[k]]).sort((a, b) => b[1] - a[1])
  return `Optimises for ${ranked[0][0].toLowerCase()} first, then ${ranked[1][0].toLowerCase()}.`
}

export default function Profile({ company }) {
  const comps = useApi('/companies')
  const cmp = useApi('/policy-compare', { company_id: company })
  const plan = useApi('/plan', { company_id: company })
  if (!comps.data || !cmp.data || !plan.data) return <div className="page"><Loading error={comps.error || cmp.error || plan.error} /></div>
  const me = comps.data.find((c) => c.company_id === company)
  const p = me.policy
  const ranked = DIMS.map(([k, l]) => ({ k, l, v: p.weights[k] })).sort((a, b) => b.v - a.v)
  const t = plan.data.totals
  const guard = [
    ['Minimum margin', pct(p.min_margin), 'No extra budget below this unit margin', 'margin'],
    ['Minimum ROAS', p.min_roas.toFixed(1) + '×', 'Reconciled, at the new budget', 'roas'],
    ['Maximum CAC', inr(p.max_cac), 'Cost to win one order', 'cac'],
    ['Inventory target', p.inventory_target_days + ' days', 'Stock cover the policy aims to hold', 'inv'],
  ]
  return (
    <div className="page">
      <section className="card identity" aria-labelledby="id-h">
        <div className="identity-main">
          <div className="eyebrow">Brand policy</div>
          <h2 id="id-h" className="winner">{me.name}</h2>
          <p className="muted" style={{ margin: 0, maxWidth: '58ch' }}>{me.description}</p>
          <div className="row wrap" style={{ marginTop: 6 }}>
            <span className="pill gold">{me.vertical}</span>
            <span className="pill">{p.risk_label}</span>
            <span className="pill">Daily budget <b className="num" style={{ color: 'var(--text)' }}>{inr(t.budget_before)}</b></span>
          </div>
        </div>
        <div className="identity-obj">
          <div className="eyebrow">Business objective</div>
          <p className="obj">{objective(p.weights)}</p>
          <p className="muted small" style={{ margin: 0 }}>Weights tilt the optimizer; guardrails below are hard limits.</p>
        </div>
      </section>

      <div className="grid g-5-7">
        <section className="card" aria-labelledby="w-h">
          <h3 id="w-h">Objective weighting</h3>
          <ul className="wlist">
            {ranked.map((d) => (
              <li key={d.k}>
                <Hint text={DIM_NOTE[d.k]} align="left"><span>{d.l}</span></Hint>
                <div className="bar"><i style={{ width: '100%', transform: `scaleX(${d.v / ranked[0].v})` }} /></div>
                <b className="num">{pct(d.v)}</b>
              </li>
            ))}
          </ul>
        </section>
        <section className="card" aria-labelledby="g-h">
          <h3 id="g-h">Guardrails</h3>
          <dl className="guards">
            {guard.map(([l, v, s, k]) => (
              <div key={l}>
                <dt><Hint k={k} text={s} align="left"><span>{l}</span></Hint></dt>
                <dd className="num">{v}</dd>
              </div>
            ))}
          </dl>
          <p className="muted small" style={{ margin: '14px 0 0' }}>A campaign that fails any guardrail cannot receive more budget.</p>
        </section>
      </div>

      <section className="card" aria-labelledby="cmp-h">
        <div className="row between wrap">
          <h3 id="cmp-h" style={{ margin: 0 }}>Same data, four policies</h3>
          <span className="muted small">What {me.name}’s campaigns would do under each brand’s priorities</span>
        </div>
        <div className="grid g4" style={{ marginTop: 12 }}>
          {cmp.data.policies.map((pol) => (
            <div className={'pcard' + (pol.policy_id === company ? ' own' : '')} key={pol.policy_id}>
              <div className="eyebrow">{pol.policy_name}{pol.policy_id === company ? ' · this brand' : ''}</div>
              <b className="num up">+{inr(pol.incremental_profit)}<small>/day</small></b>
              <span className="muted small">{pol.top[0] ? pol.top[0].title : 'No moves clear the guardrails.'}</span>
            </div>
          ))}
        </div>
        <Disclosure title="Budget change per campaign, by policy" summary={`${cmp.data.matrix.length} campaigns × 4 policies`}>
          <div className="tscroll" tabIndex={0} role="region" aria-label="Budget change per campaign by policy, scrollable">
            <table className="table">
              <thead><tr><th>Campaign</th>{ORDER.map((k) => <th key={k} className="r" style={{ color: k === company ? 'var(--gold)' : undefined }}>{cmp.data.policies.find((x) => x.policy_id === k).policy_name}{k === company ? ' ★' : ''}</th>)}</tr></thead>
              <tbody>{cmp.data.matrix.map((m) => (
                <tr key={m.campaign_id}><td><b>{m.name}</b></td>
                  {ORDER.map((k) => { const h = heat(m.by_policy[k], m.current); return <td key={k} className="r"><span className="heat" style={{ background: h.bg, color: h.fg }}>{h.t}</span></td> })}
                </tr>
              ))}</tbody>
            </table>
          </div>
          <p className="muted small" style={{ marginBottom: 0 }}>★ this brand’s own policy. Strict ROAS and margin policies cut harder; growth-weighted ones keep funding prospecting.</p>
        </Disclosure>
        <Disclosure title="How the policy is used">
          <ul className="why">
            <li>Weights tilt the optimizer: <b>utility = Σ 6·wᵢ · (profit, revenue, new-customer LTV, inventory pressure, CAC/ROAS penalties, risk)</b>.</li>
            <li>Guardrails are hard: a campaign that fails ROAS, CAC, margin or safe-stock cannot receive more budget.</li>
            <li>Policies are comparable across brands: absolute ₹ limits are rescaled by price level.</li>
          </ul>
        </Disclosure>
      </section>
    </div>
  )
}
