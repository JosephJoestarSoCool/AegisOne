import fs from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const API = 'http://127.0.0.1:8201'
const UI = 'http://127.0.0.1:4173'
const PAGES = ['Guided Demo', 'Command Center', 'AI Diagnosis', 'Budget Optimizer', 'Company Profile', 'What-If Simulator', 'ML Lab', 'Data Sources', 'Decision History']
const BRANDS = ['Nike', 'Samsung', 'Lenovo', 'Louis Vuitton', 'Supreme']

const nav = (page, name) => page.getByRole('button', { name: new RegExp('^' + name) }).click()

test('cross-origin production build: every page and brand works with no console or network errors', async ({ page }) => {
  const bad = []
  const apiHosts = new Set()
  page.on('console', (m) => ['error', 'warning'].includes(m.type()) && bad.push(`${m.type()}: ${m.text()}`))
  page.on('pageerror', (e) => bad.push('pageerror: ' + e.message))
  page.on('requestfailed', (r) => bad.push('failed ' + r.url()))
  page.on('response', (r) => { if (r.url().includes('/api/')) { apiHosts.add(new URL(r.url()).origin); if (r.status() >= 400) bad.push(`${r.status()} ${r.url()}`) } })
  await page.goto('/')
  for (const name of PAGES) {
    await nav(page, name)
    await page.waitForLoadState('networkidle')
    await expect(page.locator('#content .page')).toBeVisible()
  }
  await nav(page, 'Command Center')
  for (const brand of BRANDS) {
    await page.getByRole('button', { name: /Brand \/ company/ }).click()
    await page.getByRole('option', { name: new RegExp(brand) }).click()
    await expect(page.locator('.winner')).toBeVisible()
    await expect(page.locator('.verdict .eyebrow').first()).toContainText(brand)
    await expect(page.locator('.trap-claim')).toBeVisible()
  }
  expect([...apiHosts]).toEqual([API])          // the bundle talks to VITE_API_BASE_URL, never to a relative or localhost:8000 URL
  expect(bad).toEqual([])
})

test('approve → feedback → history, What-If and ML Lab trace work against the separate API origin', async ({ page, request }) => {
  await page.goto('/')
  await nav(page, 'Command Center')
  await page.getByRole('button', { name: /Review & approve/ }).click()
  const dlg = page.getByRole('dialog')
  await dlg.getByRole('button', { name: /Approve & simulate/ }).click()
  await expect(dlg.getByText('Approved')).toBeVisible()
  await page.keyboard.press('Escape')
  await nav(page, 'Decision History')
  const hist = await (await request.get(`${API}/api/history?company_id=nike`)).json()
  expect(hist.summary.approved).toBeGreaterThan(0)
  await nav(page, 'ML Lab')
  await expect(page.locator('.trace .tcell')).toHaveCount(4)
  await nav(page, 'What-If Simulator')
  await expect(page.locator('.cmp')).toBeVisible()
})

test('CORS: only the configured frontend origin is allowed; no wildcard', async ({ request }) => {
  const ok = await request.get(`${API}/api/health`, { headers: { Origin: UI } })
  expect(ok.headers()['access-control-allow-origin']).toBe(UI)
  const evil = await request.get(`${API}/api/health`, { headers: { Origin: 'https://evil.example' } })
  expect(evil.headers()['access-control-allow-origin']).toBeUndefined()
  const pre = await request.fetch(`${API}/api/whatif`, { method: 'OPTIONS', headers: { Origin: 'https://evil.example', 'Access-Control-Request-Method': 'POST' } })
  expect(pre.headers()['access-control-allow-origin']).toBeUndefined()
})

test('backend outage shows a friendly error, and Try again recovers', async ({ page }) => {
  let down = true
  await page.route(`${API}/api/**`, (route) => (down ? route.abort() : route.continue()))
  await page.goto('/')
  await nav(page, 'Data Sources')
  const alert = page.getByRole('alert')
  await expect(alert).toContainText('Couldn’t reach the API', { timeout: 15_000 })
  await expect(alert).not.toContainText(/Traceback|at \w+\.|localhost:8000/)
  down = false
  await alert.getByRole('button', { name: 'Try again' }).click()
  await expect(page.locator('.src').first()).toBeVisible()
})

test('server errors never leak internals to the UI', async ({ page }) => {
  await page.route(`${API}/api/data-sources`, (route) => route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"Traceback (most recent call last): secret path C:/srv"}' }))
  await page.goto('/')
  await nav(page, 'Data Sources')
  const alert = page.getByRole('alert')
  await expect(alert).toContainText('The API returned an error (500)')
  await expect(alert).not.toContainText('Traceback')
})

test('the SPA serves index.html for unknown paths (static-host fallback)', async ({ request }) => {
  const r = await request.get(`${UI}/some/deep/link`)
  expect(r.status()).toBe(200)
  expect(await r.text()).toContain('<div id="root">')
})

test('production build: deep links work and the bundle contains no localhost API URL', async ({ page }) => {
  await page.goto('/optimizer')
  await expect(page.locator('.topbar h1')).toHaveText('Budget Optimizer')
  await expect(page.locator('.winner')).toBeVisible()
  const dist = path.resolve('dist/assets')
  for (const f of fs.readdirSync(dist).filter((n) => n.endsWith('.js'))) {
    const src = fs.readFileSync(path.join(dist, f), 'utf8')
    expect(src, f).not.toMatch(/localhost:8000|127\.0\.0\.1:8000/)
  }
})
