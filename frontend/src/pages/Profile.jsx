import { PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer } from 'recharts'
import { inr, pct, useApi } from '../api'
import { Loading } from '../components'
import { C } from '../lib'

const DIMS = [['profitability', 'Profit'], ['growth', 'Growth'], ['revenue', 'Revenue'], ['inventory', 'Inventory'], ['cac', 'CAC'], ['risk', 'Risk']]
const ORDER = ['fashion', 'startup', 'electronics', 'food']

function heat(v, current) {
  if (v === 0) return { bg: 'transparent', fg: 'var(--muted)', t: '—' }
  if (v <= -current + 1) return { bg: 'rgba(248,113,113,.28)', fg: '#fecaca', t: 'PAUSE' }
  const a = Math.min(0.32, 0.08 + Math.abs(v) / 40000)
  return v > 0 ? { bg: `rgba(45,212,191,${a})`, fg: '#a7f3d0', t: '+' + inr(v) } : { bg: `rgba(248,113,113,${a})`, fg: '#fecaca', t: inr(v) }
}

export default function Profile({ company }) {
  const comps = useApi('/companies')
  const cmp = useApi('/policy-compare', { company_id: company })
  if (!comps.data || !cmp.data) return <div className="page"><Loading error={comps.error || cmp.error} /></div>
  const me = comps.data.find((c) => c.company_id === company)
  const p = me.policy
  const radar = DIMS.map(([k, l]) => ({ dim: l, weight: Math.round(p.weights[k] * 100) }))
  return (
    <div className="page">
      <div className="grid g-5-7">
        <div className="card">
          <h3>{me.name} · objective weights</h3>
          <ResponsiveContainer width="100%" height={260}>
            <RadarChart data={radar} outerRadius="72%">
              <PolarGrid stroke={C.line} />
              <PolarAngleAxis dataKey="dim" tick={{ fill: C.muted, fontSize: 12 }} />
              <Radar dataKey="weight" stroke={C.gold} fill={C.gold} fillOpacity={0.28} strokeWidth={2} isAnimationActive={false} />
            </RadarChart>
          </ResponsiveContainer>
          <div className="row wrap" style={{ gap: 8, justifyContent: 'center' }}>
            {DIMS.map(([k, l]) => <span key={k} className="pill">{l} <b className="gold num">{pct(p.weights[k])}</b></span>)}
          </div>
        </div>
        <div className="stack">
          <div className="card">
            <h3>Business context</h3>
            <p>{me.description}</p>
            <div className="row wrap" style={{ marginTop: 10 }}><span className="pill gold">{me.vertical}</span><span className="pill">{p.risk_label}</span></div>
          </div>
          <div className="grid g2">
            {[['Minimum margin', pct(p.min_margin), 'No scaling below this unit margin'], ['Minimum ROAS', p.min_roas.toFixed(1) + '×', 'Reconciled, blended at new budget'],
              ['Maximum CAC', inr(p.max_cac), 'Cost per acquired order'], ['Inventory target', p.inventory_target_days + ' days', 'Cover the policy aims to hold']].map(([l, v, s]) => (
              <div className="card kpi" key={l}><div className="label">{l}</div><div className="value num">{v}</div><div className="muted small">{s}</div></div>
            ))}
          </div>
          <div className="card"><h3>How the policy is used</h3>
            <ul className="why"><li>Weights tilt the optimizer’s objective: <b>utility = Σ 6·wᵢ · (profit, revenue, new-customer LTV, inventory pressure, CAC/ROAS penalties, risk)</b>.</li>
              <li>Guardrails are hard: a campaign that fails ROAS, CAC, margin or safe-stock cannot receive more budget.</li>
              <li>Policies are comparable across companies — absolute ₹ limits are rescaled by price level.</li></ul></div>
        </div>
      </div>

      <div className="card">
        <h3>Same data, four policies — daily budget change per campaign ({me.name} campaigns)</h3>
        <table className="table">
          <thead><tr><th>Campaign</th>{ORDER.map((k) => <th key={k} className="r" style={{ color: k === company ? 'var(--gold)' : undefined }}>{cmp.data.policies.find((x) => x.policy_id === k).policy_name}{k === company ? ' ★' : ''}</th>)}</tr></thead>
          <tbody>{cmp.data.matrix.map((m) => (
            <tr key={m.campaign_id}><td><b>{m.name}</b></td>
              {ORDER.map((k) => { const h = heat(m.by_policy[k], m.current); return <td key={k} className="r"><span className="heat" style={{ background: h.bg, color: h.fg }}>{h.t}</span></td> })}
            </tr>
          ))}</tbody>
        </table>
        <div className="muted small" style={{ marginTop: 10 }}>★ = this company’s own policy. Strict-ROAS and margin policies cut harder; growth-weighted policies keep funding prospecting.</div>
      </div>

      <div className="grid g4">
        {cmp.data.policies.map((pol) => (
          <div className="card" key={pol.policy_id} style={pol.policy_id === company ? { borderColor: 'var(--gold)' } : undefined}>
            <h3>{pol.policy_name}</h3>
            <div className="up num" style={{ fontSize: 20, fontWeight: 700 }}>+{inr(pol.incremental_profit)}<span className="muted small"> /day</span></div>
            <div className="stack" style={{ marginTop: 10, gap: 8 }}>
              {pol.top.length ? pol.top.map((t) => <div key={t.rec_id} className="small">{t.title}</div>) : <div className="muted small">No moves clear the guardrails.</div>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
