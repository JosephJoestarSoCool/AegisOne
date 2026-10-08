import { expect, test } from '@playwright/test'

/** Release-hardening sweep: every key page at desktop, tablet and phone widths. */
const VIEWPORTS = [
  { name: 'desktop 1440', width: 1440, height: 900 },
  { name: 'tablet 820', width: 820, height: 1180 },
  { name: 'mobile 390', width: 390, height: 844 },
]
const PAGES = ['Command Center', 'ML Lab', 'Data Sources', 'Budget Optimizer', 'What-If Simulator', 'Company Profile', 'Guided Demo']

async function openPage(page, name, width) {
  if (width <= 900) await page.getByRole('button', { name: 'Open navigation' }).click()
  await page.getByRole('button', { name, exact: true }).click()
  await page.waitForLoadState('networkidle')
  await expect(page.locator('#content .page')).toBeVisible()
  if (name === 'ML Lab') await expect(page.locator('.trace .tcell').first()).toBeVisible()
  if (name === 'Guided Demo') await expect(page.getByText(/Guided demo ·/)).toBeVisible()
  await page.waitForFunction(() => document.getAnimations().filter((a) => a.playState === 'running' && a.effect?.getTiming().iterations !== Infinity && !a.effect?.target?.closest?.('.pa')).length === 0, null, { timeout: 10_000 })
}

/** Elements that poke outside the viewport (outside an intentional scroller) or are clipped by their card. */
const audit = () => {
  const W = document.documentElement.clientWidth
  const out = []
  const inScroller = (el) => {
    for (let n = el.parentElement; n; n = n.parentElement) {
      const o = getComputedStyle(n).overflowX
      if (o === 'hidden' || o === 'clip') return true   // clipped on purpose (e.g. progress-bar track)
      if (o === 'auto' || o === 'scroll') return true
    }
    return false
  }
  const label = (el) => el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).join('.') : '')
  for (const el of document.querySelectorAll('#content *')) {
    const cs = getComputedStyle(el)
    if (cs.display === 'none' || cs.visibility === 'hidden') continue
    const r = el.getBoundingClientRect()
    if (!r.width || !r.height) continue
    if ((r.right > W + 1 || r.left < -1) && !inScroller(el) && !el.closest('[role="tooltip"]')) out.push('outside viewport: ' + label(el))
  }
  for (const el of document.querySelectorAll('#content .card, #content .tcell')) {
    const o = getComputedStyle(el).overflowX
    if (o !== 'auto' && o !== 'scroll' && el.scrollWidth > el.clientWidth + 1) out.push('clipped: ' + label(el))
  }
  return { over: document.documentElement.scrollWidth - innerWidth, out: [...new Set(out)].slice(0, 8) }
}

for (const vp of VIEWPORTS) {
  test.describe(vp.name, () => {
    test.use({ viewport: { width: vp.width, height: vp.height } })

    for (const name of PAGES) {
      test(`${name}: no overflow, no clipped or off-screen content`, async ({ page }) => {
        await page.goto('/')
        await openPage(page, name, vp.width)
        const res = await page.evaluate(audit)
        expect(res.over, 'horizontal page overflow').toBeLessThanOrEqual(0)
        expect(res.out).toEqual([])
      })
    }

    test('brand switcher is usable and keeps layout inside the viewport', async ({ page }) => {
      await page.goto('/')
      if (vp.width <= 900) await page.getByRole('button', { name: 'Open navigation' }).click()
      for (const brand of ['Samsung', 'Louis Vuitton']) {
        await page.getByRole('button', { name: /Brand \/ company/ }).click()
        const pop = page.locator('.brand-pop')
        await expect(pop).toBeVisible()
        const box = await pop.boundingBox()
        expect(box.x).toBeGreaterThanOrEqual(0)
        expect(box.x + box.width).toBeLessThanOrEqual(vp.width + 1)
        await page.getByRole('option', { name: new RegExp(brand) }).click()
        await expect(page.getByRole('button', { name: new RegExp('Brand / company: ' + brand) })).toBeVisible()
        if (vp.width <= 900 && !(await page.locator('.side.open').count())) await page.getByRole('button', { name: 'Open navigation' }).click()
      }
    })

    test('mobile navigation opens, reaches every page and closes', async ({ page }) => {
      test.skip(vp.width > 900, 'sidebar is permanent on desktop')
      await page.goto('/')
      const toggle = page.getByRole('button', { name: 'Open navigation' })
      await toggle.click()
      await expect(page.locator('.side.open')).toBeVisible()
      for (const name of [...PAGES, 'AI Diagnosis', 'Decision History']) {
        const b = page.getByRole('button', { name: name === 'AI Diagnosis' ? /^AI Diagnosis/ : name, exact: name !== 'AI Diagnosis' })
        await expect(b).toBeVisible()
        const box = await b.boundingBox()
        expect(box.x + box.width).toBeLessThanOrEqual(vp.width)
        expect(box.height).toBeGreaterThanOrEqual(32)
      }
      await page.getByRole('button', { name: 'ML Lab', exact: true }).click()
      await expect(page.locator('.side.open')).toHaveCount(0)
    })

    test('drawer opens inside the viewport, close is reachable, Escape returns focus', async ({ page }) => {
      await page.goto('/')
      await openPage(page, 'Command Center', vp.width)
      const trigger = page.getByRole('button', { name: 'Full analysis' })
      await trigger.scrollIntoViewIfNeeded()
      await trigger.click()
      const dlg = page.getByRole('dialog')
      await expect(dlg).toBeVisible()
      await page.waitForFunction(() => document.getAnimations().every((a) => a.playState !== 'running'))   // slide-in finished
      const box = await dlg.boundingBox()
      expect(box.x).toBeGreaterThanOrEqual(-1)
      expect(box.x + box.width).toBeLessThanOrEqual(vp.width + 1)
      expect(box.y + box.height).toBeLessThanOrEqual(vp.height + 1)
      const close = dlg.getByRole('button', { name: 'Close details' })
      const cb = await close.boundingBox()
      expect(cb.x + cb.width).toBeLessThanOrEqual(vp.width)
      await page.keyboard.press('Escape')
      await expect(dlg).toBeHidden()
      await expect(trigger).toBeFocused()
    })

    test('hover does not shift layout; keyboard focus is visible', async ({ page }) => {
      await page.goto('/')
      await openPage(page, 'Command Center', vp.width)
      const btn = page.getByRole('button', { name: /Review & approve/ })
      await btn.scrollIntoViewIfNeeded()
      const layout = () => page.evaluate(() => {
        const b = [...document.querySelectorAll('button')].find((x) => /Review & approve/.test(x.textContent))
        return { top: b.offsetTop, left: b.offsetLeft, w: b.offsetWidth, h: b.offsetHeight, doc: document.documentElement.scrollHeight }
      })
      const before = await layout()
      await btn.hover()
      await page.waitForTimeout(300)
      expect(await layout()).toEqual(before)
      await btn.focus()
      await page.keyboard.press('Tab')
      await page.keyboard.press('Shift+Tab')
      const ring = await btn.evaluate((e) => { const s = getComputedStyle(e); return { style: s.outlineStyle, width: parseFloat(s.outlineWidth) } })
      expect(ring.style).not.toBe('none')
      expect(ring.width).toBeGreaterThanOrEqual(2)
    })

    test('critical information is visible without hover (winner, profit/₹1, ML Lab trace result)', async ({ page }) => {
      await page.goto('/')
      await openPage(page, 'Command Center', vp.width)
      await expect(page.locator('.winner')).toBeVisible()
      await expect(page.locator('.hero-num b')).toBeVisible()
      await expect(page.locator('.trap-claim')).toBeVisible()
      await openPage(page, 'ML Lab', vp.width)
      await expect(page.locator('.trace-win')).toBeVisible()
      await expect(page.locator('.ov-grid')).toBeVisible()
    })
  })
}
