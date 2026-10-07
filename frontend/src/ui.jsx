import { useEffect, useId, useRef, useState } from 'react'
import Icon from './icons'

/** Plain-language metric definitions, shown on hover, keyboard focus, or tap. */
export const GLOSS = {
  roas: 'Revenue generated per ₹1 of ad spend (average, all spend so far).',
  mroas: 'Revenue from the next ₹1 of spend. Falls as a campaign saturates.',
  ppr: 'Contribution profit from the next ₹1 after COGS and the ₹1 itself: marginal ROAS × margin − 1. This is what the engine ranks on.',
  value: 'Incremental profit per ₹1 plus the company’s policy weights: growth, inventory pressure, CAC and risk.',
  margin: 'Contribution margin per unit sold: (price − unit cost) ÷ price.',
  cac: 'Marginal CAC: ad spend needed to win one more order at today’s budget.',
  cvr: 'Share of clicks that become orders.',
  inv: 'Days of stock left at the current sell-through rate.',
  risk: 'Chance the SKU stocks out before replenishment, given lead time.',
  conf: 'How much to trust this estimate: elasticity fit quality, stock safety and ROAS stability.',
  health: 'Transparent 0–100 score blending profit, ROAS, conversion, inventory fit, creative freshness and stability.',
  budget: 'Daily budget before and after the recommended move.',
}

export function Hint({ k, text, children, align }) {
  const id = useId()
  const [pinned, setPinned] = useState(false)
  const root = useRef(null)
  useEffect(() => {
    if (!pinned) return
    const away = (e) => { if (!root.current?.contains(e.target)) setPinned(false) }
    document.addEventListener('pointerdown', away)
    return () => document.removeEventListener('pointerdown', away)
  }, [pinned])
  return (
    <span className={'hint' + (pinned ? ' pinned' : '') + (align ? ' ' + align : '')} ref={root}>
      <button
        type="button" className="hint-btn" aria-describedby={id} aria-expanded={pinned}
        onClick={() => setPinned((p) => !p)} onKeyDown={(e) => e.key === 'Escape' && setPinned(false)}
      >{children}</button>
      <span role="tooltip" id={id} className="hint-pop">{text ?? GLOSS[k]}</span>
    </span>
  )
}

/** Label + value pair. The label carries the definition; the value stays visually primary. */
export function Metric({ k, label, value, tone, text }) {
  return (
    <div className="metric">
      <Hint k={k} text={text}>{label}</Hint>
      <b className={'num ' + (tone || '')}>{value}</b>
    </div>
  )
}

export function Health({ h }) {
  const tone = h.status === 'Healthy' ? 'good' : h.status === 'Watch' ? 'warn' : 'bad'
  return (
    <span className={'health ' + tone}>
      <i className="health-dot" aria-hidden="true" />
      <b className="num">{h.score}</b>
      <span className="health-label">{h.status}</span>
    </span>
  )
}

export function Drawer({ open, onClose, title, kicker, children }) {
  const panel = useRef(null)
  const returnTo = useRef(null)
  useEffect(() => {
    if (!open) return
    returnTo.current = document.activeElement
    const t = setTimeout(() => panel.current?.querySelector('[data-autofocus]')?.focus(), 30)
    const onKey = (e) => {
      if (e.key === 'Escape') { e.stopPropagation(); onClose() }
      if (e.key !== 'Tab') return
      const f = panel.current?.querySelectorAll('button, [href], input, select, [tabindex]:not([tabindex="-1"])')
      if (!f?.length) return
      const first = f[0], last = f[f.length - 1]
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      clearTimeout(t)
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
      returnTo.current?.focus?.()
    }
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="drawer-wrap">
      <div className="drawer-scrim" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={title} ref={panel}>
        <header className="drawer-head">
          <div>{kicker && <small>{kicker}</small>}<h2>{title}</h2></div>
          <button className="icon-btn" data-autofocus onClick={onClose} aria-label="Close details"><Icon name="close" /></button>
        </header>
        <div className="drawer-body">{children}</div>
      </aside>
    </div>
  )
}

export function Section({ title, children }) {
  return <section className="dsec"><h4>{title}</h4>{children}</section>
}

export function Bars({ items }) {
  return (
    <div className="stack" style={{ gap: 8 }}>
      {items.map((p) => (
        <div className="driver" key={p.label}>
          <span>{p.label} <span className="muted">({Math.round(p.weight * 100)}%)</span></span>
          <div className="bar"><i style={{ width: '100%', transform: `scaleX(${Math.max(0.02, p.score / 100)})`, background: p.score >= 60 ? 'var(--teal)' : p.score >= 35 ? 'var(--gold)' : 'var(--red)' }} /></div>
          <span className="num" style={{ textAlign: 'right' }}>{p.score}</span>
        </div>
      ))}
    </div>
  )
}
