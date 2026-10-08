import { useEffect, useRef, useState } from 'react'

/** Global brand / company selector (top-left). Listbox popover, fully keyboard operable. */
export default function BrandSwitcher({ companies, brands, value, onChange }) {
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const root = useRef(null)
  const trigger = useRef(null)
  const optRefs = useRef([])
  const current = companies?.find((c) => c.company_id === value)
  const meta = (id) => brands?.find((b) => b.company_id === id)

  const openMenu = () => {
    setActive(Math.max(0, companies.findIndex((c) => c.company_id === value)))
    setOpen(true)
  }
  const close = (refocus = true) => {
    setOpen(false)
    if (refocus) trigger.current?.focus()
  }
  const choose = (id) => {
    if (id !== value) onChange(id)
    close()
  }

  useEffect(() => { if (open) optRefs.current[active]?.focus() }, [open, active])
  useEffect(() => {
    if (!open) return
    const away = (e) => { if (!root.current?.contains(e.target)) setOpen(false) }
    document.addEventListener('pointerdown', away)
    return () => document.removeEventListener('pointerdown', away)
  }, [open])

  const onKey = (e) => {
    const n = companies.length
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((i) => (i + 1) % n) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => (i - 1 + n) % n) }
    else if (e.key === 'Home') { e.preventDefault(); setActive(0) }
    else if (e.key === 'End') { e.preventDefault(); setActive(n - 1) }
    else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(companies[active].company_id) }
    else if (e.key === 'Escape') { e.preventDefault(); close() }
    else if (e.key === 'Tab') setOpen(false)
  }

  return (
    <div className="brand-switch" ref={root}>
      <div className="brand-kicker">AegisOne · Marketing CFO</div>
      <button
        ref={trigger} className="brand-trigger" aria-haspopup="listbox" aria-expanded={open}
        aria-label={`Brand / company: ${current?.name ?? 'loading'}. Change company`}
        disabled={!companies?.length}
        onClick={() => (open ? close(false) : openMenu())}
        onKeyDown={(e) => { if (!open && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) { e.preventDefault(); openMenu() } }}
      >
        <span className="brand-mark" aria-hidden="true">{meta(value)?.ticker ?? '₹'}</span>
        <span className="brand-name">
          <b>{current?.name ?? '…'}</b>
          <span>{current?.vertical ?? ''}</span>
        </span>
        <svg className="chev" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </button>
      {open && (
        <div className="brand-pop" role="presentation">
          <div className="brand-pop-head">
            <small>Brand / company</small>
            <b>{current?.name}</b>
            <span>{meta(value)?.policy_summary ?? current?.description}</span>
            <span className="brand-pop-note">Demo policy · public product data · simulated ads</span>
          </div>
          <ul role="listbox" aria-label="Companies" onKeyDown={onKey} aria-activedescendant={`co-${companies[active]?.company_id}`}>
            {companies.map((c, i) => (
              <li
                key={c.company_id} id={`co-${c.company_id}`} role="option" aria-selected={c.company_id === value}
                tabIndex={i === active ? 0 : -1} ref={(el) => (optRefs.current[i] = el)}
                onClick={() => choose(c.company_id)} onMouseMove={() => active !== i && setActive(i)}
                className={i === active ? 'is-active' : ''}
              >
                <span className="opt-name">{c.name}<small>{meta(c.company_id)?.policy_summary ?? c.vertical}</small></span>
                {c.company_id === value && <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="m3 7.5 2.7 2.7L11 4.8" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
