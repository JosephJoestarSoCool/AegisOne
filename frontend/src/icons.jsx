/** Minimal stroke icon set (24px grid, currentColor). */
const P = {
  play: 'M7 5.5v13l11-6.5z',
  command: 'M4 13a8 8 0 1 1 16 0M12 13l4-4M7 20h10',
  diagnosis: 'M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18',
  optimizer: 'M4 8h13m0 0-3-3m3 3-3 3M20 16H7m0 0 3-3m-3 3 3 3',
  profile: 'M5 20V9l7-5 7 5v11M9 20v-6h6v6',
  whatif: 'M5 7h9m4 0h1M5 17h1m4 0h9M14 4v6M10 14v6',
  history: 'M4 12a8 8 0 1 0 3-6.2M4 4v4h4M12 8v4l3 2',
  menu: 'M4 7h16M4 12h16M4 17h16',
  close: 'M6 6l12 12M18 6 6 18',
  info: 'M12 11v5M12 8h.01M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z',
  check: 'm5 12.5 4.5 4.5L19 7.5',
  chevron: 'm6 9 6 6 6-6',
  right: 'm9 6 6 6-6 6',
  alert: 'M12 9v4M12 17h.01M10.3 3.9 2.4 17.5A2 2 0 0 0 4.1 20.5h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z',
  arrow: 'M5 12h14m0 0-5-5m5 5-5 5',
  ml: 'M5 19V9m5 10V5m5 14v-7m5 7V8',
  data: 'M4 6c0-1.1 3.6-2 8-2s8 .9 8 2-3.6 2-8 2-8-.9-8-2zm0 0v12c0 1.1 3.6 2 8 2s8-.9 8-2V6M4 12c0 1.1 3.6 2 8 2s8-.9 8-2',
  sparkle: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z',
}

export default function Icon({ name, size = 18, className, ...rest }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" {...rest}>
      <path d={P[name]} />
    </svg>
  )
}
