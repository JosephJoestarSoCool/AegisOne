/** Small editorial primitives shared across pages. Pure presentation: no data, no logic. */

/** Tracked uppercase micro label. */
export function SectionLabel({ children, index, as: Tag = 'div', ...rest }) {
  return (
    <Tag className="slabel" {...rest}>
      {index != null && <span className="slabel-i num">{String(index).padStart(2, '0')}</span>}
      <span>{children}</span>
    </Tag>
  )
}

export function Hairline({ strong = false }) {
  return <hr className={'hairline' + (strong ? ' strong' : '')} aria-hidden="true" />
}

/** Oversized stacked page heading with an optional lead paragraph and a ghosted background word. */
export function PageHero({ kicker, lines, lead, ghost, id, level = 2, children }) {
  const Tag = `h${level}`
  return (
    <header className="phero">
      {ghost && <span className="wm" aria-hidden="true">{ghost}</span>}
      <SectionLabel>{kicker}</SectionLabel>
      <Tag className="mega" id={id}>{lines.map((l, i) => <span key={i}>{l}</span>)}</Tag>
      {lead && <p className="lead">{lead}</p>}
      {children}
    </header>
  )
}

/** Label + large figure. `tone` colours the figure semantically. */
export function BigStat({ label, value, sub, tone, size = 'l', hint }) {
  return (
    <div className={'bigstat ' + size}>
      <div className="slabel">{hint ?? label}</div>
      <b className={'num ' + (tone || '')}>{value}</b>
      {sub && <span className="muted small">{sub}</span>}
    </div>
  )
}
