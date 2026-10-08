import { Hint } from './ui'

/** Four data classes the UI always keeps apart. */
const PROV = {
  public: { label: 'Public data', note: 'Taken from a named third-party public dataset. Not brand first-party data.' },
  assumption: { label: 'Demo policy', note: 'A demo assumption (policy, unit cost, stock, lead time). Not the company’s real strategy or books.' },
  model: { label: 'Model prediction', note: 'Output of the trained conversion-propensity model.' },
  sim: { label: 'Simulated', note: 'Simulated marketing performance derived from public product/sales signals. Not brand ad-account data.' },
}

export function Tag({ kind, children }) {
  const p = PROV[kind]
  return (
    <Hint text={p.note} align="left">
      <span className={'ptag ' + kind}><i aria-hidden="true" />{children ?? p.label}</span>
    </Hint>
  )
}

export function Legend() {
  return (
    <div className="legend row wrap" aria-label="Data provenance legend">
      {Object.keys(PROV).map((k) => <Tag key={k} kind={k} />)}
    </div>
  )
}
