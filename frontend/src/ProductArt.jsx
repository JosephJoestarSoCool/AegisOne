import { useCallback, useEffect, useRef, useState } from 'react'
import { galleryFor } from './productGallery'

/**
 * Full-bleed editorial product-art poster for the Budget Optimizer's right panel.
 * The photograph fills the whole panel; all text and controls sit ON the image over a light gradient. Only the selected
 * brand's own images are shown (manifest key = the global company id). The parent remounts this component on a brand change
 * (`key`), which resets the index and drops the previous brand's image immediately.
 *
 * Fit: `cover` when the crop would be modest; otherwise the whole photograph is shown over a blurred, darkened enlargement of
 * itself, so there is never an empty colour block around the picture.
 */

const ROTATE_MS = 6200
const FADE_MS = 1400
const MAX_CROP = 0.45
const pad = (n) => String(n).padStart(2, '0')

function Media({ item, brand, total, panelRatio, failed, onFail }) {
  if (failed) {
    return (
      <div className="pa-missing" role="img" aria-label={`${brand} product archive image ${item.index} unavailable`}>
        <b>{brand}</b><span>Product image unavailable</span>
      </div>
    )
  }
  const r = item.w / item.h
  const crop = 1 - Math.min(r / panelRatio, panelRatio / r)
  const cover = crop <= MAX_CROP
  return (
    <div className="pa-media">
      {!cover && <img className="pa-bg" src={item.src} alt="" aria-hidden="true" decoding="async" draggable="false" />}
      <img
        className={'pa-img ' + (cover ? 'cover' : 'contain')} src={item.src} alt={`${brand} product archive, image ${item.index} of ${total}`}
        decoding="async" draggable="false" onError={() => onFail(item.index)}
      />
    </div>
  )
}

export default function ProductArt({ companyId, brand }) {
  const items = galleryFor(companyId)
  const n = items.length
  const [cur, setCur] = useState(0)
  const [leaving, setLeaving] = useState(null)
  const [playing, setPlaying] = useState(true)
  const [held, setHeld] = useState(false)          // hover / keyboard focus inside the panel pauses rotation
  const [info, setInfo] = useState(false)
  const [ratio, setRatio] = useState(0.5)
  const [failed, setFailed] = useState(() => new Set())
  const [reduced, setReduced] = useState(() => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches)
  const timer = useRef(null)
  const curRef = useRef(0)
  const stage = useRef(null)

  useEffect(() => {
    if (typeof matchMedia !== 'function') return undefined
    const mq = matchMedia('(prefers-reduced-motion: reduce)')
    const on = () => setReduced(mq.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [])
  useEffect(() => () => clearTimeout(timer.current), [])
  useEffect(() => {
    const el = stage.current
    if (!el || typeof ResizeObserver !== 'function') return undefined
    const ro = new ResizeObserver(([e]) => { const { width, height } = e.contentRect; if (width && height) setRatio(Math.round((width / height) * 20) / 20) })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const go = useCallback((to) => {
    const from = curRef.current
    if (to === from) return
    curRef.current = to
    setLeaving(from)
    setCur(to)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setLeaving(null), FADE_MS)
  }, [])

  // Next frame that has not failed to load.
  const nextOk = useCallback((from) => {
    for (let k = 1; k <= n; k++) { const j = (from + k) % n; if (!failed.has(items[j].index)) return j }
    return from
  }, [failed, items, n])

  // Warm the browser cache with the next image only; the rest stay unrequested until their turn.
  useEffect(() => {
    if (n < 2) return
    const j = nextOk(cur)
    if (j !== cur) { const im = new Image(); im.src = items[j].src }
  }, [cur, items, n, nextOk])

  // Rotation: never while hidden, held, paused, or when the user prefers reduced motion.
  useEffect(() => {
    if (n < 2 || !playing || held || reduced) return undefined
    const id = setInterval(() => { if (!document.hidden) go(nextOk(curRef.current)) }, ROTATE_MS)
    return () => clearInterval(id)
  }, [n, playing, held, reduced, go, nextOk, cur])

  const onFail = useCallback((index) => setFailed((s) => (s.has(index) ? s : new Set(s).add(index))), [])

  if (!n) return null
  const it = items[cur]
  const running = playing && !held && !reduced && n > 1
  return (
    <section
      className={'pa bleed' + (reduced ? ' reduced' : '')} aria-label={`${brand} product archive`}
      onMouseEnter={() => setHeld(true)} onMouseLeave={() => setHeld(false)} onFocus={() => setHeld(true)} onBlur={() => setHeld(false)}
    >
      <div className="pa-stage" ref={stage}>
        {leaving != null && items[leaving] && (
          <figure key={'o' + leaving} className="pa-layer out" aria-hidden="true">
            <Media item={items[leaving]} brand={brand} total={n} panelRatio={ratio} failed={failed.has(items[leaving].index)} onFail={onFail} />
          </figure>
        )}
        <figure key={'i' + cur} className="pa-layer in">
          <Media item={it} brand={brand} total={n} panelRatio={ratio} failed={failed.has(it.index)} onFail={onFail} />
        </figure>
      </div>
      <div className="pa-shade" aria-hidden="true" />

      <div className="pa-top">
        <span className="pa-brand"><b>{brand}</b><span>Product archive</span></span>
        <button type="button" className="pa-info-btn" aria-expanded={info} aria-controls="pa-info" aria-label="About this imagery" onClick={() => setInfo((v) => !v)}>i</button>
      </div>
      {info && (
        <p id="pa-info" className="pa-info" role="note">
          Brand imagery supplied for demo context. Owned by the respective brands; no affiliation or endorsement implied.
        </p>
      )}

      <div className="pa-bottom">
        <div className="pa-row">
          <div className="pa-title"><span>Product archive</span><span className="pa-count num" aria-label={`Image ${cur + 1} of ${n}`}>{pad(cur + 1)} <em>/</em> {pad(n)}</span></div>
          {n > 1 && !reduced && (
            <button type="button" className="pa-pause" aria-pressed={!playing} onClick={() => setPlaying((v) => !v)}>{playing ? 'Pause' : 'Play'}</button>
          )}
        </div>
        <div className="pa-bars" role="group" aria-label="Choose image">
          {items.map((x, i) => (
            <button key={x.src} type="button" className={'pa-bar' + (i === cur ? ' on' : '')} aria-label={`${pad(i + 1)} ${brand} product archive`} aria-current={i === cur ? 'true' : undefined} onClick={() => go(i)}>
              <i key={i === cur ? 'a' + cur : 'x'} className={i === cur && running ? 'run' : ''} style={i === cur ? { animationDuration: ROTATE_MS + 'ms' } : undefined} />
            </button>
          ))}
        </div>
      </div>
    </section>
  )
}
