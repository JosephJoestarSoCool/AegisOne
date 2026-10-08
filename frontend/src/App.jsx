import { lazy, Suspense, useEffect, useState } from 'react'
import { useApi } from './api'
import BrandSwitcher from './BrandSwitcher'
import { Loading } from './components'
import Icon from './icons'

const lazyPage = (name) => lazy(() => import(`./pages/${name}.jsx`))
const CommandCenter = lazyPage('CommandCenter')
const Demo = lazyPage('Demo')
const Diagnosis = lazyPage('Diagnosis')
const DataSources = lazyPage('DataSources')
const History = lazyPage('History')
const MLLab = lazyPage('MLLab')
const Optimizer = lazyPage('Optimizer')
const Profile = lazyPage('Profile')
const WhatIf = lazyPage('WhatIf')

const NAV = [
  ['demo', 'Guided Demo', 'play'],
  ['command', 'Command Center', 'command'],
  ['diagnosis', 'AI Diagnosis', 'diagnosis'],
  ['optimizer', 'Budget Optimizer', 'optimizer'],
  ['profile', 'Company Profile', 'profile'],
  ['whatif', 'What-If Simulator', 'whatif'],
  ['mllab', 'ML Lab', 'ml'],
  ['sources', 'Data Sources', 'data'],
  ['history', 'Decision History', 'history'],
]
const TITLES = {
  demo: ['Guided Demo', 'data → diagnose → compare → decide → simulate → approve → learn'],
  command: ['Command Center', 'Where should the next ₹1 of ad spend go?'],
  diagnosis: ['AI Diagnosis', 'What happened → probable cause → confidence → action'],
  optimizer: ['Budget Optimizer', 'Maximise expected incremental profit inside the company’s policy'],
  profile: ['Company Profile', 'Objectives, guardrails — and how other policies would decide'],
  whatif: ['What-If Simulator', 'Change budget, stock, price or priorities — the decision re-solves'],
  mllab: ['ML Lab', 'How the model learns → what it predicts → how the CFO uses it → the final decision'],
  sources: ['Data Sources', 'Public data vs demo assumptions vs model vs simulation'],
  history: ['Decision History', 'prediction → action → actual outcome → error → updated confidence'],
}

export default function App() {
  const [page, setPage] = useState('demo')
  const [company, setCompany] = useState('nike')
  const [focus, setFocus] = useState(null)
  const [preset, setPreset] = useState(null)
  const [nav, setNav] = useState(false)
  const comps = useApi('/companies')
  const brands = useApi('/brands')
  useEffect(() => { document.documentElement.dataset.brand = company }, [company])
  const diag = useApi('/overview', { company_id: company })
  const go = (p, f = null, pre = null) => { setNav(false); setPage(p); setFocus(f); if (pre) setPreset(pre) }
  const [title, sub] = TITLES[page]
  const view = {
    demo: <Demo go={go} setCompany={setCompany} companies={comps.data} />,
    command: <CommandCenter company={company} go={go} />,
    diagnosis: <Diagnosis company={company} focus={focus} go={go} />,
    optimizer: <Optimizer company={company} />,
    profile: <Profile company={company} />,
    whatif: <WhatIf company={company} preset={preset?.sku?.startsWith(company + '-') ? preset : null} />,
    mllab: <MLLab company={company} />,
    sources: <DataSources company={company} />,
    history: <History company={company} />,
  }[page]
  return (
    <div className="shell">
      <a className="skip" href="#content">Skip to content</a>
      <aside className={'side' + (nav ? ' open' : '')} id="sidebar" aria-label="Primary">
        <BrandSwitcher companies={comps.data} brands={brands.data} value={company} onChange={(id) => { setCompany(id); setFocus(null); setNav(false) }} />
        {NAV.map(([k, label, icon], i) => (
          <div key={k}>
            {i === 1 && <div className="nav-sep" />}
            <button className="nav-btn" aria-current={page === k ? 'page' : undefined} onClick={() => go(k)}>
              <Icon name={icon} />{label}
              {k === 'diagnosis' && diag.data && <span className="badge">{diag.data.anomaly_count}</span>}
            </button>
          </div>
        ))}
        <div className="side-foot">Public product data + simulated ad performance. No brand ad accounts.<br />DataQuest 3.0</div>
      </aside>
      {nav && <div className="side-scrim" onClick={() => setNav(false)} />}
      <main className="main">
        <header className="topbar">
          <button className="icon-btn menu-btn" aria-label="Open navigation" aria-expanded={nav} aria-controls="sidebar" onClick={() => setNav(!nav)}><Icon name="menu" /></button>
          <div><h1>{title}</h1><div className="sub">{sub}</div></div>
          <div className="spacer" />
        </header>
        <div key={page + (page === 'demo' ? '' : company)} id="content"><Suspense fallback={<div className="page"><Loading /></div>}>{view}</Suspense></div>
      </main>
    </div>
  )
}
