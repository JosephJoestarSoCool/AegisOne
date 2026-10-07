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
  const ov = await api(request, '/overview?company_id=fashion')
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
    const skus = new Set(ov.candidates.map((c) => c.sku_name))
    const names = await page.locator('.ptable tbody .prow .row-btn b').allInnerTexts()
    expect(names.length).toBeGreaterThan(0)
    for (const n of names) expect(skus.has(n)).toBe(true)          // every row belongs to this brand
    winners.add(ov.next_rupee.sku_id)
  }
  expect(winners.size).toBe(companies.length)
})

test('portfolio ranks candidates, winner first, rows expand to secondary metrics', async ({ page, request }) => {
  const ov = await api(request, '/overview?company_id=fashion')
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
  const co = companies.find((c) => c.company_id === 'electronics')
  const ov = await api(request, '/overview?company_id=electronics')
  await openCommandCenter(page)
  await switchBrand(page, co.name)
  expect(ov.roas_trap.active).toBe(true)
  await expect(page.locator('.trap-msg')).toHaveText(ov.roas_trap.message)
  await expect(page.locator('.trap-row').first()).toContainText(nameOf(ov.roas_trap.roas_leader))
})

test('why-not alternatives list reasons and open a drawer that returns focus', async ({ page, request }) => {
  const ov = await api(request, '/overview?company_id=fashion')
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
  const exp = await (await request.post('/api/whatif', { data: { company_id: 'fashion', scenario: { sku_overrides: { 'fashion-scarf': { on_hand: 207 } } } } })).json()
  await page.goto('/')
  await page.getByRole('button', { name: 'What-If Simulator' }).click()
  await expect(page.locator('.cmp')).toBeVisible()
  await expect(page.getByText('Winner unchanged')).toBeVisible()
  await page.getByLabel('Product').selectOption({ label: 'Silk Scarf' })
  await page.getByLabel(/Inventory/).fill('207')
  await expect(page.getByText('Winner changed', { exact: true })).toBeVisible()
  await expect(page.locator('.cmp .wcard').nth(1).locator('.wname')).toContainText(exp.next_rupee.after.sku_name)
  await expect(page.locator('.banner')).toContainText('lead time')
})

test('approve → outcome → decision history', async ({ page, request }) => {
  const before = await api(request, '/history?company_id=fashion')
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
  const after = await api(request, '/history?company_id=fashion')
  expect(after.summary.approved).toBeGreaterThan(before.summary.approved)
  const fresh = after.items.find((i) => !before.items.some((b) => b.rec_id === i.rec_id))
  expect(fresh.status).toBe('approved')
  await expect(page.locator('.table tbody tr').filter({ hasText: fresh.title.slice(0, 30) }).first()).toBeVisible()
})

test('guided demo walks data → feedback and opens the simulator on the demo company', async ({ page, request }) => {
  await page.goto('/')
  await switchBrand(page, (await api(request, '/companies')).find((c) => c.company_id === 'electronics').name)
  await page.getByRole('button', { name: 'Guided Demo' }).click()
  await expect(page.getByRole('heading', { name: /Guided demo/ })).toBeVisible()
  for (const next of ['Diagnosis', 'Decision', 'What-if', 'Feedback']) await page.getByRole('button', { name: new RegExp('^Next: ' + next) }).click()
  await page.getByRole('button', { name: /Approve & simulate/ }).click()
  await expect(page.getByText('Approved & scored')).toBeVisible()
  await page.locator('.stepper').getByRole('button', { name: /What-if/ }).click()
  await page.getByRole('button', { name: /Open in simulator/ }).click()
  await expect(page.locator('.cmp')).toBeVisible()
  await expect(page.getByLabel('Product')).toHaveValue('fashion-scarf')
  await expect(page.getByText('Winner changed', { exact: true })).toBeVisible()
})

test('loading skeleton and API error states', async ({ page }) => {
  await page.route('**/api/overview*', async (route) => { await new Promise((r) => setTimeout(r, 1200)); await route.continue() })
  await page.goto('/')
  await page.getByRole('button', { name: 'Command Center' }).click()
  await expect(page.getByRole('status', { name: 'Loading' })).toBeVisible()
  await page.unroute('**/api/overview*')
  await page.route('**/api/plan*', (route) => route.abort())
  await page.getByRole('button', { name: 'Budget Optimizer' }).click()
  await expect(page.getByRole('alert')).toContainText('Couldn’t reach the API')
})

for (const name of ['Command Center', 'AI Diagnosis', 'Budget Optimizer', 'Company Profile', 'What-If Simulator', 'Decision History', 'Guided Demo']) {
  test(`a11y: no serious axe violations on ${name}`, async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name }).click()
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(900)   // let entrance animations finish so axe sees final colours
    const res = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()
    const bad = res.violations.filter((v) => ['serious', 'critical'].includes(v.impact))
    expect(bad.map((v) => `${v.id}: ${v.nodes.slice(0, 3).map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([])
  })
}

test('no horizontal overflow at tablet and mobile widths', async ({ page }) => {
  for (const w of [820, 390]) {
    await page.setViewportSize({ width: w, height: 844 })
    await page.goto('/')
    for (const name of ['Command Center', 'Budget Optimizer', 'Company Profile', 'Decision History', 'What-If Simulator', 'AI Diagnosis']) {
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
  for (const name of ['Guided Demo', 'Command Center', 'AI Diagnosis', 'Budget Optimizer', 'Company Profile', 'What-If Simulator', 'Decision History']) {
    await page.getByRole('button', { name }).click()
    await page.waitForLoadState('networkidle')
  }
  await switchBrand(page, 'Electronics')
  await page.waitForLoadState('networkidle')
  expect(bad).toEqual([])
})
