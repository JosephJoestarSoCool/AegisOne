import { useState } from 'react'
import { useApi } from '../api'
import { Loading } from '../components'
import { PageHero } from '../editorial'
import { Legend, Tag } from '../provenance'


function Source({ s, i, label, current, open, toggle }) {
  return (
    <article className={'src' + (current ? ' current' : '')} aria-labelledby={'src-' + s.id}>
      <div className="src-idx num" aria-hidden="true">{String(i).padStart(2, '0')}</div>
      <div className="src-brand"><b id={'src-' + s.id}>{label}</b><span className="eyebrow">{s.scope}{current ? ' · selected brand' : ''}</span></div>
      <div className="src-main">
        <h3 className="src-name">{s.name}</h3>
        <p className="small"><span className="muted">Contains: </span>{s.contains}</p>
        <p className="small down"><span className="muted">Does NOT contain: </span>{s.does_not_contain}</p>
        <p className="small"><span className="muted">Used for: </span>{s.used_for}</p>
        <div className="row wrap small">
          <span><span className="muted">Source: </span>{s.publisher}</span>
          <span className="muted">·</span><span>~{s.source_rows?.toLocaleString('en-IN')} source rows</span>
          <span className="muted">·</span><b className={s.license === 'Unknown' ? 'gold' : ''}>License: {s.license}</b>
        </div>
      </div>
      <div className="src-side"><Tag kind="public" /><button className="linkarrow" aria-expanded={open} onClick={toggle}>Limitations <span aria-hidden="true">→</span></button></div>
      {open && (
        <dl className="src-dl">
          <div><dt>Limitations</dt><dd>{s.limitations}</dd></div>
          <div><dt>Type</dt><dd>{s.type}</dd></div>
          <div><dt>Date range</dt><dd>{s.date_range}</dd></div>
          <div><dt>License</dt><dd>{s.license}</dd></div>
          <div><dt>Dataset URL</dt><dd><a href={s.url} target="_blank" rel="noreferrer">{s.url}</a></dd></div>
          <div><dt>Ingested</dt><dd>{s.ingested} · <code>python -m app.ingest</code> → processed/{s.processed_file}</dd></div>
          <div><dt>Transformation</dt><dd>{s.notes}</dd></div>
        </dl>
      )}
    </article>
  )
}

export default function DataSources({ company }) {
  const src = useApi('/data-sources')
  const brands = useApi('/brands')
  const [open, setOpen] = useState(null)
  if (!src.data || !brands.data) return <div className="page"><Loading error={src.error || brands.error} /></div>
  const b = brands.data.find((x) => x.company_id === company)
  const sorted = [...src.data].sort((a, z) => (z.id === company) - (a.id === company))
  const labelOf = (id) => brands.data.find((x) => x.company_id === id)?.name ?? 'Marketing data'
  return (
    <div className="page">
      <PageHero kicker="Data archive · provenance" lines={['Data', 'archive']} ghost="SRC"
        lead="Every dataset, what it contains, what it does not, and its license. Nothing here is first-party brand advertising data." />
      <p className="note small">Budget Optimizer product-art photographs are brand-owned images supplied locally for visual context only. They are not part of any dataset below and imply no affiliation or endorsement.</p>
      <section className="card" aria-labelledby="prov-h">
        <div className="row between wrap"><h3 id="prov-h" style={{ margin: 0 }}>{b.name} · what is real, assumed, modelled and simulated</h3><Legend /></div>
        <div className="grid g3 prov-cols">
          <div><Tag kind="public" /><ul className="plain small">{b.provenance.public.map((x) => <li key={x}>{x}</li>)}</ul><p className="muted small">From {b.public_source.name}.</p></div>
          <div><Tag kind="assumption" /><ul className="plain small">{b.provenance.assumption.map((x) => <li key={x}>{x}</li>)}</ul><p className="muted small">{b.policy_rationale}</p></div>
          <div><Tag kind="sim" /><ul className="plain small">{b.provenance.simulated.map((x) => <li key={x}>{x}</li>)}</ul><p className="muted small">{b.sim_label}. No brand ad-account data is used or claimed.</p></div>
        </div>
      </section>
      <div className="archive">
        {sorted.map((s, i) => <Source key={s.id} s={s} i={i + 1} label={s.id === 'marketing' ? 'Marketing' : labelOf(s.id)} current={s.id === company} open={open === s.id} toggle={() => setOpen(open === s.id ? null : s.id)} />)}
      </div>
    </div>
  )
}
