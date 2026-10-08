import { useState } from 'react'
import { inr, pct, useApi } from '../api'
import { Loading } from '../components'
import Icon from '../icons'
import { fx } from '../lib'
import { PageHero, SectionLabel } from '../editorial'
import { Legend, Tag } from '../provenance'

const STORY = [
  ['How the model learns', 'Real public ad data → funnel features → cross-validated fit.'],
  ['What it predicts', 'Approved purchases per click for each campaign.'],
  ['How it influences the CFO', 'A bounded multiplier on expected orders. Nothing else.'],
  ['How the decision is made', 'Policy, guardrails and the optimizer decide the next ₹1.'],
]

function pipeline(card, trace, brand) {
  const v = card.validation
  return [
    ['Public data', 'ml', `${card.n_records.toLocaleString('en-IN')} usable ads from a public Facebook-ad dataset. Product names and prices for ${brand} come from separate public catalogs.`],
    ['Data cleaning', 'ml', 'Drop ads with zero clicks; reject negative values and clicks > impressions. Raw and processed files are stored separately.'],
    ['Feature engineering', 'ml', `${card.n_features} scale-free funnel features: log CTR, CPC and CPM indices vs the portfolio median, impression index. This lets USD training data transfer to any brand.`],
    ['Model training', 'ml', `${card.model_type} chosen over ${Object.keys(card.candidates).length - 1} alternative by cross-validated deviance. Target: ${card.target}.`],
    ['Validation', 'ml', `${v.method.split(',')[0]}: deviance ${v.cv_deviance} vs constant-rate baseline ${v.baseline_deviance} (−${v.deviance_reduction_pct}%). Calibration ratio ${v.calibration_ratio}.`],
    ['Prediction', 'ml', trace ? `For ${brand}, every campaign gets a predicted conversion rate, then a multiplier clipped to ${trace.model.clip[0]}–${trace.model.clip[1]}× at ${pct(trace.model.weight)} weight.` : 'Loading…'],
    ['Business policy', 'cfo', 'Brand weights (profit, growth, revenue, inventory, CAC, risk) turn raw profit into policy-weighted value. Demo policy, not the company’s real strategy.'],
    ['Portfolio optimizer', 'cfo', 'Concave utilities, hard guardrails (margin, ROAS, CAC, stock) and a greedy marginal-utility solver. Deterministic; the source of truth.'],
    ['Next ₹1 decision', 'cfo', trace ? (trace.decision.winner ? `Winner: ${trace.decision.winner}.` : 'No campaign clears the guardrails.') : 'Loading…'],
  ]
}

function Overview({ card, sources }) {
  const v = card.validation
  const rows = [
    ['Model', card.name], ['Type', card.model_type], ['Training data', `${card.n_records.toLocaleString('en-IN')} records`],
    ['Features', card.n_features], ['Target', card.target],
    ['Validation', `CV deviance −${v.deviance_reduction_pct}% vs baseline`], ['Version', card.version],
  ]
  return (
    <section className="card" aria-labelledby="ov-h">
      <div className="row between wrap"><h3 id="ov-h" style={{ margin: 0 }}>Model overview</h3><Tag kind="model" /></div>
      <dl className="ov-grid">
        {rows.map(([k, val]) => <div key={k}><dt>{k}</dt><dd>{val}</dd></div>)}
        <div className="wide"><dt>Training data source</dt><dd>{sources?.find((x) => x.id === card.data_source)?.name ?? card.data_source} · {sources?.find((x) => x.id === card.data_source)?.publisher} · <Tag kind="public" /></dd></div>
      </dl>
      <p className="note small">{card.honest_reading}</p>
      {sources && (
        <details className="more"><summary>Public data coverage behind each brand</summary>
          <table className="table"><thead><tr><th>Dataset</th><th className="r">Source rows</th><th>Limitation</th></tr></thead>
            <tbody>{sources.map((x) => <tr key={x.id}><td>{x.name}<div className="muted small">{x.scope}</div></td><td className="r num">{x.source_rows.toLocaleString('en-IN')}</td><td className="small">{x.limitations}</td></tr>)}</tbody></table>
        </details>
      )}
    </section>
  )
}

function Pipeline({ steps }) {
  const [i, setI] = useState(0)
  return (
    <section className="card" aria-labelledby="pl-h">
      <div className="row between wrap"><h3 id="pl-h" style={{ margin: 0 }}>From data to the next ₹1</h3>
        <span className="muted small"><i className="dot ml" /> ML layer predicts &nbsp; <i className="dot cfo" /> CFO layer decides</span></div>
      <ol className="pipe" aria-label="Pipeline stages">
        {steps.map(([name, layer], k) => (
          <li key={name}>
            <button className={'pstage ' + layer} aria-pressed={i === k} onClick={() => setI(k)}><span className="num">{k + 1}</span>{name}</button>
            {k < steps.length - 1 && <Icon name="right" size={12} className="muted sep" />}
          </li>
        ))}
      </ol>
      <p className="stage-detail" aria-live="polite"><b>{steps[i][0]}.</b> {steps[i][2]}</p>
    </section>
  )
}

function Features({ card }) {
  const [open, setOpen] = useState(card.features[0].feature)
  const max = Math.max(...card.features.map((f) => f.importance), 0.01)
  return (
    <section className="card" aria-labelledby="ft-h">
      <h3 id="ft-h">Top model features · out-of-fold permutation importance</h3>
      <div className="stack" style={{ gap: 4 }}>
        {card.features.map((f) => {
          const on = open === f.feature
          return (
            <div key={f.feature} className={'feat' + (on ? ' open' : '')}>
              <button className="feat-head" aria-expanded={on} onClick={() => setOpen(on ? null : f.feature)}>
                <span className="feat-name">{f.label}</span>
                <span className="bar"><i style={{ width: '100%', transform: `scaleX(${Math.max(0.02, f.importance / max)})` }} /></span>
                <span className="num">{pct(f.importance)}</span>
                <span className={'pill ' + (f.direction === 'raises' ? 'teal' : 'red')}>{f.direction}</span>
                <Icon name="chevron" size={14} className={'caret' + (on ? ' open' : '')} />
              </button>
              {on && (
                <dl className="feat-body">
                  <div><dt>What it means</dt><dd>{f.what}</dd></div>
                  <div><dt>Why it matters</dt><dd>{f.why}</dd></div>
                  <div><dt>How it affects the prediction</dt><dd>{f.effect}</dd></div>
                </dl>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}

function Validation({ card }) {
  const q = card.quartile_lift
  const top = Math.max(...q.map((x) => Math.max(x.actual, x.predicted)))
  return (
    <section className="card" aria-labelledby="va-h">
      <h3 id="va-h">Does it rank ads correctly? · held-out quartiles</h3>
      <p className="muted small">Ads sorted by out-of-fold predicted rate and split in four. If the model works, actual purchases per click rise with the quartile.</p>
      <div className="quart">
        {q.map((x) => (
          <div key={x.quartile} className="qrow">
            <span className="muted small">Q{x.quartile}</span>
            <div className="qbars" aria-hidden="true">
              <i className="pred" style={{ transform: `scaleX(${x.predicted / top})` }} />
              <i className="act" style={{ transform: `scaleX(${x.actual / top})` }} />
            </div>
            <span className="num small">{(x.actual * 100).toFixed(1)}% <span className="muted">actual · {(x.predicted * 100).toFixed(1)}% predicted</span></span>
          </div>
        ))}
      </div>
      <details className="more"><summary>Model comparison</summary>
        <table className="table"><thead><tr><th>Candidate</th><th className="r">CV deviance</th><th className="r">vs baseline</th></tr></thead>
          <tbody>{Object.entries(card.candidates).map(([n, c]) => <tr key={n}><td>{n}{n === card.model_type && <span className="pill gold" style={{ marginLeft: 8 }}>selected</span>}</td><td className="r num">{c.cv_deviance.toFixed(5)}</td><td className="r num up">−{c.deviance_reduction_pct}%</td></tr>)}</tbody></table>
      </details>
    </section>
  )
}

function Cell({ title, kind, children }) {
  return <div className="tcell"><div className="row between"><span className="eyebrow">{title}</span>{kind && <Tag kind={kind} />}</div>{children}</div>
}
const KV = ({ k, v, tone }) => <div className="kv"><span className="muted">{k}</span><b className={'num ' + (tone || '')}>{v}</b></div>

function Trace({ company, brand, tr, setCid }) {
  const plan = useApi('/plan', { company_id: company })
  if (!tr.data || !plan.data) return <section className="card"><Loading error={tr.error || plan.error} /></section>
  const t = tr.data, i = t.inputs, m = t.model, c = t.cfo, d = t.decision
  const cands = plan.data.candidates
  const rank = cands.find((x) => x.campaign_id === t.campaign_id)?.rank
  return (
    <section className="card" aria-labelledby="tr-h">
      <div className="row between wrap">
        <h3 id="tr-h" style={{ margin: 0 }}>Prediction trace · {brand}</h3>
        <label className="small muted">Candidate{' '}
          <select value={t.campaign_id} onChange={(e) => setCid(e.target.value)} aria-label="Trace candidate">
            {cands.map((x) => <option key={x.campaign_id} value={x.campaign_id}>#{x.rank} {x.campaign}{x.campaign_id === d.winner_campaign_id ? ' ★' : ''}</option>)}
          </select>
        </label>
      </div>
      <div className="trace">
        <Cell title="1 · Inputs" kind="sim">
          <KV k="Product" v={i.product} /><KV k="Platform" v={i.platform} /><KV k="Daily spend" v={inr(i.daily_spend)} />
          <KV k="Contribution margin" v={pct(i.contribution_margin)} /><KV k="Inventory" v={`${Math.round(i.inventory_days)} d (lead ${Math.round(i.lead_time)} d)`} />
          <details className="more"><summary>More inputs</summary>
            <KV k="ROAS" v={i.roas.toFixed(2) + '×'} /><KV k="CAC" v={inr(i.cac)} /><KV k="CVR" v={(i.cvr * 100).toFixed(2) + '%'} />
            <KV k="CTR" v={(i.ctr * 100).toFixed(2) + '%'} /><KV k="CPC" v={inr(i.cpc, 1)} /><KV k="Unit price" v={inr(i.price)} />
          </details>
        </Cell>
        <Icon name="arrow" className="tarrow muted" />
        <Cell title="2 · Model prediction" kind="model">
          <KV k="Conversion rate / click" v={(m.conv_rate_per_click * 100).toFixed(2) + '%'} tone="gold" />
          <KV k="vs portfolio average" v={m.relative_to_portfolio.toFixed(2) + '×'} />
          <KV k="Engine multiplier" v={m.multiplier.toFixed(3) + '×'} />
          <KV k="Incremental revenue / ₹1k" v={inr(m.incremental_revenue_per_step)} />
          <KV k="Incremental profit / ₹1k" v={inr(m.incremental_profit_per_step)} tone={m.incremental_profit_per_step >= 0 ? 'up' : 'down'} />
          <KV k="Confidence" v={pct(m.confidence)} />
          <p className="muted small">Expected daily orders {m.orders_before_ml.toFixed(2)} → {m.orders_after_ml.toFixed(2)} after the bounded ML adjustment ({pct(m.weight)} weight, clip {m.clip[0]}–{m.clip[1]}×).</p>
        </Cell>
        <Icon name="arrow" className="tarrow muted" />
        <Cell title="3 · CFO decision" kind="assumption">
          <KV k="Opportunity score" v={c.opportunity_score} />
          <KV k="Raw profit / ₹1" v={fx(c.profit_per_rupee)} />
          <KV k="Policy-weighted value / ₹1" v={c.policy_value_per_rupee.toFixed(2)} tone="gold" />
          <KV k="Risk adjustment / ₹1" v={c.risk_adjustment_per_rupee.toFixed(3)} tone="down" />
          <KV k="Guardrails" v={c.eligible ? 'clear' : 'gated'} tone={c.eligible ? 'up' : 'down'} />
          {c.gate_reason && <p className="down small">{c.gate_reason}</p>}
          <details className="more"><summary>Policy contribution by dimension</summary>
            {Object.entries(c.policy_parts).map(([k, v]) => <KV key={k} k={k} v={v.toFixed(3)} tone={v >= 0 ? 'up' : 'down'} />)}
          </details>
        </Cell>
        <Icon name="arrow" className="tarrow muted" />
        <Cell title="4 · Final decision">
          <p className="q">Where should the next ₹1 go?</p>
          <b className="trace-win">{d.winner ?? 'No eligible campaign'}</b>
          {d.winner && <>
            <p className="small">{d.platform} · {inr(d.current)} → <b>{inr(d.recommended)}</b>/day · <span className="up">{fx(d.profit_per_rupee)}</span> per ₹1</p>
            <p className="muted small">{t.is_winner ? 'This candidate won.' : `This candidate ranked #${rank}; the winner is shown.`}</p>
          </>}
        </Cell>
      </div>
      <div className="tstory" aria-label="How the prediction leads to the decision">
        <div><Tag kind="model" /><p>{i.product} × {i.platform} has a predicted conversion rate of {(m.conv_rate_per_click * 100).toFixed(2)}% per click, {m.relative_to_portfolio.toFixed(2)}× the {brand} portfolio.</p></div>
        <div><Tag kind="sim">Business context</Tag><p>{Math.round(i.inventory_days)} days of inventory, {pct(i.contribution_margin)} contribution margin.</p></div>
        <div><Tag kind="assumption" /><p>{brand} demo policy: {plan.data.policy.risk_label.toLowerCase()}; margin floor {pct(plan.data.policy.min_margin)}, ROAS floor {plan.data.policy.min_roas.toFixed(1)}×.</p></div>
        <div><Tag kind="assumption">Decision engine</Tag><p>Policy-weighted value {c.policy_value_per_rupee.toFixed(2)} per ₹1 ranks #{rank} of {cands.length} after guardrails.</p></div>
        <div><p><b>Final:</b> {d.winner ? `Allocate the next ₹1 to ${d.winner}.` : 'Hold: nothing clears the guardrails.'}</p></div>
      </div>
      <p className="note small">{t.ml_effect.changed
        ? 'With the ML adjustment switched off, a different campaign would win the next ₹1: the model nudged the ranking, and the policy engine confirmed it.'
        : 'Switching the ML adjustment off would not change the winner: the deterministic engine, not the model, drives this decision.'}</p>
    </section>
  )
}

function ModelNote({ card }) {
  const v = card.validation
  const top = card.features[0]
  return (
    <section className="modelnote" aria-label="Model note">
      <div className="mn-quote">
        <SectionLabel>Model note</SectionLabel>
        <p>The model predicts demand signal.<br />The CFO engine decides capital allocation.</p>
      </div>
      <dl className="mn-facts">
        <div><dt>Model</dt><dd>{card.model_type}</dd></div>
        <div><dt>Target</dt><dd>{card.target}</dd></div>
        <div><dt>Baseline improvement</dt><dd className="num">+{v.deviance_reduction_pct}%</dd></div>
        <div><dt>Top feature</dt><dd>{top.label} <b className="num">{(top.importance * 100).toFixed(0)}%</b></dd></div>
      </dl>
    </section>
  )
}

export default function MLLab({ company }) {
  const card = useApi('/ml/card')
  const brands = useApi('/brands')
  const sources = useApi('/data-sources')
  const [cid, setCid] = useState(null)
  const tr = useApi('/ml/trace', cid ? { company_id: company, campaign_id: cid } : { company_id: company })
  if (!card.data || !brands.data) return <div className="page"><Loading error={card.error || brands.error} /></div>
  const brand = brands.data.find((b) => b.company_id === company).name
  return (
    <div className="page">
      <PageHero kicker="ML Lab · research notes" lines={['Model', 'intelligence']} ghost="ML"
        lead="A bounded demand signal feeds a deterministic capital-allocation engine. Everything below is read from the trained model card and the live backend." />
      <ModelNote card={card.data} />
      <ol className="story-row" aria-label="How to read this page">
        {STORY.map(([h, p], k) => <li key={h}><span className="num">{k + 1}</span><b>{h}</b><span className="muted small">{p}</span></li>)}
      </ol>
      <Legend />
      <Overview card={card.data} sources={sources.data} />
      <Pipeline steps={pipeline(card.data, tr.data, brand)} />
      <div className="grid g-7-5"><Features card={card.data} /><Validation card={card.data} /></div>
      <Trace company={company} brand={brand} tr={tr} setCid={setCid} />
    </div>
  )
}
