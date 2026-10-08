/** Fail fast unless the backend under test is healthy and is the current multi-brand build. */
export default async function globalSetup() {
  const base = 'http://127.0.0.1:8101/api'
  const get = async (p) => {
    const r = await fetch(base + p)
    if (!r.ok) throw new Error(`E2E backend check failed: GET ${p} -> ${r.status}`)
    return r.json()
  }
  if ((await get('/health')).status !== 'ok') throw new Error('E2E backend unhealthy')
  const ids = (await get('/companies')).map((c) => c.company_id).sort()
  const want = ['lenovo', 'lv', 'nike', 'samsung', 'supreme']
  if (JSON.stringify(ids) !== JSON.stringify(want)) throw new Error(`E2E backend is not the current build: companies = ${ids}`)
  await get('/ml/card')
  await get('/data-sources')
}
