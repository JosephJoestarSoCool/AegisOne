import { useEffect, useId, useRef, useState } from 'react'
import Icon from './icons'
import { GLOSS } from './lib'


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

/** Collapsible section: clean by default, detail on demand. */
export function Disclosure({ title, summary, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen)
  const id = useId()
  return (
    <section className={'disc' + (open ? ' open' : '')}>
      <button type="button" className="disc-head" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)}>
        <span className="disc-title">{title}</span>
        {summary && !open && <span className="muted small disc-sum">{summary}</span>}
        <Icon name="chevron" size={16} className="caret" />
      </button>
      {open && <div className="disc-body" id={id}>{children}</div>}
    </section>
  )
}
