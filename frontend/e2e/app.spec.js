import fs from 'node:fs'
import path from 'node:path'
import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

const api = async (request, path) => (await request.get('/api' + path)).json()
const nameOf = (x) => `${x.sku_name} × ${x.platform}`

test.beforeAll(async ({ request }) => { await request.post('/api/reset', { data: {} }) })

async function openCommandCenter(page) {
  await page.goto('/')
  await page.getByRole('button', { name: 'Command Center' }).click()
  await expect(page.locator('.verdict')).toBeVisible()
}

async function switchBrand(page, name) {
  await page.getByRole('button', { name: /Brand \/ company/ }).click()
  await page.getByRole('option', { name: new RegExp(name) }).click()
}

test('next ₹1 verdict renders the engine winner, with why-it-won', async ({ page, request }) => {
  const ov = await api(request, '/overview?company_id=nike')
  await openCommandCenter(page)
  const w = ov.next_rupee
  await expect(page.locator('.winner')).toHaveText(`${w.sku_name} × ${w.platform}`)
  await expect(page.locator('.verdict-why li')).toHaveCount(w.why_won.length)
  await expect(page.locator('.hero-num b')).toHaveText('₹' + w.profit_per_rupee.toFixed(2))
})

test('brand switching changes every decision input with no leakage', async ({ page, request }) => {
  await openCommandCenter(page)
  const companies = await api(request, '/companies')
  const winners = new Set()
  for (const co of companies) {
    await switchBrand(page, co.name)
    const ov = await api(request, `/overview?company_id=${co.company_id}`)
    await expect(page.locator('.winner')).toHaveText(`${ov.next_rupee.sku_name} × ${ov.next_rupee.platform}`)
    await expect(page.locator('.verdict .eyebrow').first()).toContainText(co.name)
    const skus = new Set(ov.candidates.map((c) => c.sku_name.toLowerCase()))   // names render uppercase via CSS
    const names = await page.locator('.ptable tbody .prow .row-btn b').allInnerTexts()
    expect(names.length).toBeGreaterThan(0)
    for (const n of names) expect(skus.has(n.toLowerCase())).toBe(true)          // every row belongs to this brand
    winners.add(ov.next_rupee.sku_id)
  }
  expect(winners.size).toBe(companies.length)
})

test('portfolio ranks candidates, winner first, rows expand to secondary metrics', async ({ page, request }) => {
  const ov = await api(request, '/overview?company_id=nike')
  await openCommandCenter(page)
  const rows = page.locator('.ptable tbody .prow')
  await expect(rows.first()).toHaveClass(/win/)
  await expect(rows).toHaveCount(Math.min(8, ov.candidates.length))
  await rows.first().locator('.row-btn').click()
  for (const l of ['ROAS', 'Margin', 'Marginal CAC', 'CVR', 'Inventory', 'Confidence']) {
    await expect(page.locator('.prow-detail .hint-btn', { hasText: new RegExp('^' + l + '$') })).toBeVisible()
  }
})

test('ROAS trap explanation reflects the live comparison', async ({ page, request }) => {
  const companies = await api(request, '/companies')
  const co = companies.find((c) => c.company_id === 'lenovo')
  const ov = await api(request, '/overview?company_id=lenovo')
  await openCommandCenter(page)
  await switchBrand(page, co.name)
  expect(ov.roas_trap.active).toBe(true)
  await expect(page.locator('.trap-msg')).toHaveText(ov.roas_trap.message)
  await expect(page.locator('.trap-row').first()).toContainText(nameOf(ov.roas_trap.roas_leader))
})

test('why-not alternatives list reasons and open a drawer that returns focus', async ({ page, request }) => {
  const ov = await api(request, '/overview?company_id=nike')
  await openCommandCenter(page)
  const alts = page.locator('.list-item.alt')
  await expect(alts).toHaveCount(3)
  await expect(alts.first()).toContainText(ov.next_rupee.alternatives[0].why_lost[0])
  await alts.first().focus()
  await alts.first().press('Enter')
  const dlg = page.getByRole('dialog')
  await expect(dlg).toContainText('Why it ranks lower')
  await page.keyboard.press('Escape')
  await expect(dlg).toBeHidden()
  await expect(alts.first()).toBeFocused()
})

test('metric hints open on keyboard focus', async ({ page }) => {
  await openCommandCenter(page)
  await page.locator('.verdict .hint-btn').first().focus()
  await expect(page.getByRole('tooltip').first()).toBeVisible()
})

test('what-if: constraining stock changes the next-₹1 winner, computed by the engine', async ({ page, request }) => {
  const demo = await api(request, '/demo')
  const stock = demo.step4_whatif.stock_units
  const exp = await (await request.post('/api/whatif', { data: { company_id: 'nike', scenario: demo.scenario } })).json()
  const tgtName = exp.baseline.next_rupee.sku_name
  await page.goto('/')
  await page.getByRole('button', { name: 'What-If Simulator' }).click()
  await expect(page.locator('.cmp')).toBeVisible()
  await expect(page.getByText('Winner unchanged')).toBeVisible()
  await page.getByLabel('Product').selectOption({ label: tgtName })
  const inv = page.getByLabel(/Inventory/)
  const step = Number(await inv.getAttribute('step'))
  await inv.fill(String(Math.floor(stock / step) * step))
  await expect(page.getByText('Winner changed', { exact: true })).toBeVisible()
  await expect(page.locator('.cmp .wcard').nth(1).locator('.wname')).toContainText(exp.next_rupee.after.sku_name)
  await expect(page.locator('.banner')).toContainText('lead time')
})

test('approve → outcome → decision history', async ({ page, request }) => {
  const before = await api(request, '/history?company_id=nike')
  await openCommandCenter(page)
  await page.getByRole('button', { name: /Review & approve/ }).click()
  const dlg = page.getByRole('dialog')
  await expect(dlg).toContainText('Recommended action')
  await dlg.getByRole('button', { name: /Approve & simulate/ }).click()
  await expect(dlg.getByText('Approved')).toBeVisible()
  await expect(dlg).toContainText('predicted')
  await expect(dlg).toContainText('actual')
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: 'Decision History' }).click()
  const after = await api(request, '/history?company_id=nike')
  expect(after.summary.approved).toBeGreaterThan(before.summary.approved)
  const fresh = after.items.find((i) => !before.items.some((b) => b.rec_id === i.rec_id))
  expect(fresh.status).toBe('approved')
  await expect(page.locator('.table tbody tr').filter({ hasText: fresh.title.slice(0, 30) }).first()).toBeVisible()
})

test('guided demo tells the full story and ends on the calculated next-₹1 winner', async ({ page, request }) => {
  const demo = await api(request, '/demo')
  await page.goto('/')
  await switchBrand(page, (await api(request, '/companies')).find((c) => c.company_id === 'lenovo').name)
  await page.getByRole('button', { name: 'Guided Demo' }).click()
  await expect(page.getByText(/Guided demo · Nike/)).toBeVisible()
  for (const next of ['Diagnose', 'Compare', 'Decide', 'Simulate', 'Approve']) await page.getByRole('button', { name: new RegExp('^Next: ' + next) }).click()
  await page.getByRole('button', { name: /Approve & simulate/ }).click()
  await expect(page.getByText('prediction → actual → error → confidence')).toBeVisible()
  const win = demo.step_compare.next_rupee
  await expect(page.locator('.final .winner')).toHaveText(`${win.sku_name} × ${win.platform}`)
  await page.locator('.story').getByRole('button', { name: 'Simulate' }).click()
  await page.getByRole('button', { name: /Open in the simulator/ }).click()
  await expect(page.locator('.cmp')).toBeVisible()
  await expect(page.getByLabel('Product')).toHaveValue(demo.target_sku)
  await expect(page.getByText('Winner changed', { exact: true })).toBeVisible()
})

test('profile and optimizer surface policy and decision hierarchy', async ({ page, request }) => {
  const plan = await api(request, '/plan?company_id=nike')
  await page.goto('/')
  await page.getByRole('button', { name: 'Budget Optimizer' }).click()
  await expect(page.locator('.winner')).toHaveText(`${plan.next_rupee.sku_name} × ${plan.next_rupee.platform}`)
  await expect(page.getByText(/Why .* lost/)).toBeVisible()
  await page.locator('.prow .row-btn').first().click()
  await expect(page.locator('.prow-detail .hint-btn', { hasText: /^ROAS$/ })).toBeVisible()
  await page.getByRole('button', { name: 'Company Profile' }).click()
  await expect(page.getByText(/Optimises for/)).toBeVisible()
  await expect(page.locator('.guards dd')).toHaveCount(4)
  await page.getByRole('button', { name: /Budget change per campaign/ }).click()
  await expect(page.getByRole('region', { name: /by policy/ })).toBeVisible()
})

test('loading skeleton and API error states', async ({ page }) => {
  await page.route('**/api/overview*', async (route) => { await new Promise((r) => setTimeout(r, 1200)); await route.continue() })
  await page.goto('/')
  await page.getByRole('button', { name: 'Command Center' }).click()
  await expect(page.getByRole('status', { name: 'Loading' })).toBeVisible()
  await expect(page.locator('.verdict')).toBeVisible()      // the delayed request has completed
  await page.unroute('**/api/overview*')
  await page.route('**/api/plan*', (route) => route.abort())
  await page.getByRole('button', { name: 'Budget Optimizer' }).click()
  await expect(page.getByRole('alert')).toContainText('Couldn’t reach the API', { timeout: 15_000 })   // after the client's retries
  await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible()
})

for (const name of ['Command Center', 'AI Diagnosis', 'Budget Optimizer', 'Company Profile', 'What-If Simulator', 'Decision History', 'Guided Demo', 'ML Lab', 'Data Sources']) {
  test(`a11y: no serious axe violations on ${name}`, async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name }).click()
    await page.waitForLoadState('networkidle')
    if (name === 'Guided Demo') await expect(page.getByText(/Guided demo ·/)).toBeVisible()
    if (name === 'ML Lab') await expect(page.locator('.trace .tcell').first()).toBeVisible()
    await page.waitForFunction(() => document.getAnimations().filter((a) => a.playState === 'running' && a.effect?.getTiming().iterations !== Infinity && !a.effect?.target?.closest?.('.pa')).length === 0, null, { timeout: 10_000 })
    await page.waitForTimeout(300)   // let entrance animations finish so axe sees final colours
    const res = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()
    const bad = res.violations.filter((v) => ['serious', 'critical'].includes(v.impact))
    expect(bad.map((v) => `${v.id}: ${v.nodes.slice(0, 3).map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([])
  })
}

test('no horizontal overflow at tablet and mobile widths', async ({ page }) => {
  for (const w of [820, 390]) {
    await page.setViewportSize({ width: w, height: 844 })
    await page.goto('/')
    for (const name of ['Command Center', 'Budget Optimizer', 'Company Profile', 'Decision History', 'What-If Simulator', 'AI Diagnosis', 'ML Lab', 'Data Sources']) {
      await page.getByRole('button', { name: 'Open navigation' }).click()
      await page.getByRole('button', { name }).click()
      await page.waitForTimeout(1800)
      const over = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)
      expect.soft(over, `${name} @${w}`).toBeLessThanOrEqual(0)
    }
  }
})

test('no console errors, React warnings or failed requests while touring every page', async ({ page }) => {
  const bad = []
  page.on('console', (m) => ['error', 'warning'].includes(m.type()) && bad.push(`${m.type()}: ${m.text()}`))
  page.on('pageerror', (e) => bad.push('pageerror: ' + e.message))
  page.on('response', (r) => r.status() >= 400 && bad.push(`${r.status()} ${r.url()}`))
  page.on('requestfailed', (r) => bad.push('failed ' + r.url()))
  await page.goto('/')
  for (const name of ['Guided Demo', 'Command Center', 'AI Diagnosis', 'Budget Optimizer', 'Company Profile', 'What-If Simulator', 'ML Lab', 'Data Sources', 'Decision History']) {
    await page.getByRole('button', { name }).click()
    await page.waitForLoadState('networkidle')
  }
  await switchBrand(page, 'Lenovo')
  await page.waitForLoadState('networkidle')
  expect(bad).toEqual([])
})

test('brand tour Nike → Samsung → Lenovo → Louis Vuitton → Supreme on Command Center, ML Lab and Data Sources', async ({ page, request }) => {
  await openCommandCenter(page)
  const tour = ['Nike', 'Samsung', 'Lenovo', 'Louis Vuitton', 'Supreme']
  const companies = await api(request, '/companies')
  const seen = new Set()
  for (const name of tour) {
    await switchBrand(page, name)
    const id = companies.find((c) => c.name === name).company_id
    const ov = await api(request, `/overview?company_id=${id}`)
    await expect(page.locator('.winner')).toHaveText(`${ov.next_rupee.sku_name} × ${ov.next_rupee.platform}`)
    await expect(page.locator('.ctx')).toContainText(name)
    await expect(page.locator('.trap-claim')).toHaveText('High ROAS ≠ high incremental profit')
    seen.add(ov.next_rupee.sku_name)
    await page.getByRole('button', { name: 'ML Lab' }).click()
    const tr = await api(request, `/ml/trace?company_id=${id}`)
    await expect(page.locator('.trace-win')).toHaveText(tr.decision.winner)
    await expect(page.getByRole('heading', { name: new RegExp('Prediction trace · ' + name) })).toBeVisible()
    await page.getByRole('button', { name: 'Data Sources' }).click()
    await expect(page.locator('.src.current')).toBeVisible()
    await page.getByRole('button', { name: 'Command Center' }).click()
  }
  expect(seen.size).toBe(tour.length)
})

test('ML Lab: model facts match the trained card; features expand; pipeline stages are selectable', async ({ page, request }) => {
  const card = await api(request, '/ml/card')
  await page.goto('/')
  await page.getByRole('button', { name: 'ML Lab' }).click()
  await expect(page.locator('.ov-grid')).toContainText(card.model_type)
  await expect(page.locator('.ov-grid')).toContainText(card.version)
  await expect(page.locator('.feat-head')).toHaveCount(card.features.length)
  await page.locator('.feat-head').nth(1).click()
  await expect(page.locator('.feat-body')).toContainText('Why it matters')
  await page.getByRole('button', { name: /Validation/ }).click()
  await expect(page.locator('.stage-detail')).toContainText('deviance')
  await expect(page.locator('.trace .tcell')).toHaveCount(4)
  const sel = page.getByLabel('Trace candidate')
  const options = await sel.locator('option').count()
  await sel.selectOption({ index: options - 1 })
  await expect(page.locator('.trace-win')).not.toHaveText('')
})

test('Data Sources: every dataset states what it does not contain', async ({ page, request }) => {
  const src = await api(request, '/data-sources')
  await page.goto('/')
  await page.getByRole('button', { name: 'Data Sources' }).click()
  await expect(page.locator('.src')).toHaveCount(src.length)
  await expect(page.getByText('Does NOT contain:')).toHaveCount(src.length)
  await expect(page.getByText('License: Unknown')).toHaveCount(src.filter((x) => x.license === 'Unknown').length)
  for (const x of src) await expect(page.getByText(x.scope).first()).toBeVisible()
  await page.locator('.src').first().getByRole('button', { name: /Limitations/ }).click()
  await expect(page.locator('.src-dl').first()).toContainText('License')
})

test.describe('Optimizer product art (local brand images)', () => {
  const BRANDS = [['Samsung', 'samsung', 'samsung'], ['Nike', 'nike', 'nike'], ['Lenovo', 'lenovo', 'lenovo'], ['Louis Vuitton', 'lv', 'louis-vuitton'], ['Supreme', 'supreme', 'supreme']]
  const onDisk = (folder) => fs.readdirSync(path.resolve('public/products', folder)).length
  const bars = (page) => page.locator('.pa-bar')
  const srcs = (page) => page.locator('.pa img').evaluateAll((els) => els.map((e) => new URL(e.src).pathname))
  const openOptimizer = async (page) => { await page.goto('/'); await page.getByRole('button', { name: 'Budget Optimizer' }).click(); await expect(bars(page).first()).toBeVisible() }

  test('each brand shows only its own images, resets on switch, and every image loads', async ({ page }) => {
    const bad = []
    const requested = []
    page.on('console', (m) => m.type() === 'error' && bad.push(m.text()))
    page.on('response', (r) => { const u = new URL(r.url()); if (u.pathname.startsWith('/products/')) { requested.push(u.pathname); if (r.status() !== 200) bad.push(r.status() + ' ' + u.pathname) } })
    page.on('requestfailed', (r) => bad.push('failed ' + r.url()))
    await openOptimizer(page)
    for (const [label, , folder] of BRANDS) {
      await page.getByRole('button', { name: /Brand \/ company/ }).click()
      await page.getByRole('option', { name: new RegExp(label) }).click()
      await expect(page.locator('.pa-brand b')).toHaveText(label)
      await expect(bars(page)).toHaveCount(onDisk(folder))
      await expect(page.locator('.pa-count')).toContainText('01')                      // index reset on every switch
      const n = await bars(page).count()
      for (let i = 0; i < n; i++) {
        await bars(page).nth(i).click()
        await expect(page.locator('.pa-count')).toContainText(String(i + 1).padStart(2, '0'))
        await expect.poll(() => page.locator('.pa-layer.in .pa-img').evaluate((e) => e.complete && e.naturalWidth > 0)).toBe(true)
        for (const s of await srcs(page)) expect(s.startsWith('/products/' + folder + '/')).toBe(true)   // never another brand's image
      }
      await page.waitForTimeout(1600)                                                  // leaving layer gone
      for (const s of await srcs(page)) expect(s.startsWith('/products/' + folder + '/')).toBe(true)
    }
    expect(requested.length).toBeGreaterThan(0)
    expect(bad).toEqual([])
  })

  test('opens on the first image, rotates slowly and never moves the decision; Pause works', async ({ page }) => {
    await page.clock.install()
    await openOptimizer(page)
    await page.mouse.move(0, 0)                                                        // hover/focus inside the panel pauses rotation
    await expect(page.locator('.pa-count')).toContainText('01')
    await page.waitForFunction(() => document.getAnimations().every((a) => a.playState !== 'running' || a.effect?.target?.closest?.('.pa')))
    const y0 = (await page.locator('.winner').boundingBox()).y
    const idx = async () => Number((await page.locator('.pa-count').innerText()).slice(0, 2))
    const i0 = await idx()
    await page.clock.fastForward(6600)
    await expect.poll(idx).not.toBe(i0)                                                // advanced on its own
    expect((await page.locator('.winner').boundingBox()).y).toBe(y0)                   // rotation never shifts the financial decision
    await page.getByRole('button', { name: 'Pause' }).click()
    await page.mouse.move(0, 0)
    const held = await idx()
    await page.clock.fastForward(20000)
    expect(await idx()).toBe(held)
    await page.getByRole('button', { name: 'Play' }).click()
    await page.mouse.move(0, 0)
    await page.clock.fastForward(6600)
    await expect.poll(idx).not.toBe(held)
  })

  test('the image is full-bleed: it fills the whole panel, text sits on it, the disclaimer is tucked behind an info control', async ({ page }) => {
    await openOptimizer(page)
    const poster = await page.locator('.poster').boundingBox()
    const art = await page.locator('.pa.bleed').boundingBox()
    expect(Math.abs(art.x - poster.x) + Math.abs(art.y - poster.y) + Math.abs(art.width - poster.width) + Math.abs(art.height - poster.height)).toBeLessThan(2)
    const stage = await page.locator('.pa-stage').boundingBox()
    expect(stage.width).toBeGreaterThanOrEqual(poster.width - 1)                       // no inner card / padding
    expect(stage.height).toBeGreaterThanOrEqual(poster.height - 1)
    const inside = (b) => b.x >= poster.x - 1 && b.y >= poster.y - 1 && b.x + b.width <= poster.x + poster.width + 1 && b.y + b.height <= poster.y + poster.height + 1
    for (const sel of ['.pa-brand', '.pa-count', '.pa-pause', '.pa-bars', '.pa-info-btn']) expect(inside(await page.locator(sel).boundingBox())).toBe(true)
    await expect(page.getByText('Brand imagery supplied for demo context')).toBeHidden()
    await page.getByRole('button', { name: 'About this imagery' }).click()
    await expect(page.getByText('Brand imagery supplied for demo context')).toBeVisible()
    await expect(page.getByText(/Why .* lost/)).toBeVisible()                           // the optimizer's explanation is still on the page
  })

  test('prefers-reduced-motion: no auto-rotation, simple fade only, still usable by keyboard', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.clock.install()
    await openOptimizer(page)
    await page.clock.fastForward(20000)
    await expect(page.locator('.pa-count')).toContainText('01')
    await expect(page.getByRole('button', { name: 'Pause' })).toHaveCount(0)
    await bars(page).nth(2).focus()
    await page.keyboard.press('Enter')
    await expect(page.locator('.pa-count')).toContainText('03')
    const anim = await page.locator('.pa-layer.in').evaluate((e) => getComputedStyle(e).animationName)
    expect(anim).toBe('pa-fade')
  })

  test('a missing image falls back gracefully (no broken-image icon) and rotation skips it', async ({ page }) => {
    await page.route('**/products/nike/02.jpg', (route) => route.abort())
    await page.clock.install()
    await openOptimizer(page)
    await page.getByRole('button', { name: /Brand \/ company/ }).click()
    await page.getByRole('option', { name: /Nike/ }).click()
    await bars(page).nth(1).click()
    await expect(page.locator('.pa-missing')).toContainText('Product image unavailable')
    await expect(page.locator('.pa-layer.in .pa-img')).toHaveCount(0)
    await page.mouse.move(0, 0)
    await page.clock.fastForward(6600)
    await expect(page.locator('.pa-count')).toContainText('03')
    for (let i = 0; i < 6; i++) {
      await page.clock.fastForward(6600)
      await expect(page.locator('.pa-count')).not.toContainText('02')      // the failed frame is skipped in every cycle
    }
  })
})
