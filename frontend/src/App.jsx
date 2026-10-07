import { useState } from 'react'
import { useApi } from './api'
import CommandCenter from './pages/CommandCenter'
import Demo from './pages/Demo'
import Diagnosis from './pages/Diagnosis'
import History from './pages/History'
import Optimizer from './pages/Optimizer'
import Profile from './pages/Profile'
import WhatIf from './pages/WhatIf'

const NAV = [
  ['demo', 'Guided Demo', '▶'],
  ['command', 'Command Center', '◎'],
  ['diagnosis', 'AI Diagnosis', '✦'],
  ['optimizer', 'Budget Optimizer', '⇄'],
  ['profile', 'Company Profile', '◇'],
  ['whatif', 'What-If Simulator', '⌁'],
  ['history', 'Decision History', '↺'],
]
const TITLES = {
  demo: ['Guided Demo', 'data → diagnosis → decision → what-if → feedback'],
  command: ['Command Center', 'Where should the next ₹1 of ad spend go?'],
  diagnosis: ['AI Diagnosis', 'What happened → probable cause → confidence → action'],
  optimizer: ['Budget Optimizer', 'Maximise expected incremental profit inside the company’s policy'],
  profile: ['Company Profile', 'Objectives, guardrails — and how other policies would decide'],
  whatif: ['What-If Simulator', 'Change budget, stock, price or priorities — the decision re-solves'],
  history: ['Decision History', 'prediction → action → actual outcome → error → updated confidence'],
}

export default function App() {
  const [page, setPage] = useState('demo')
  const [company, setCompany] = useState('fashion')
  const [focus, setFocus] = useState(null)
  const [preset, setPreset] = useState(null)
  const comps = useApi('/companies')
  const diag = useApi('/overview', { company_id: company })
  const go = (p, f = null, pre = null) => { setPage(p); setFocus(f); if (pre) setPreset(pre) }
  const [title, sub] = TITLES[page]
  const view = {
    demo: <Demo go={go} setCompany={setCompany} />,
    command: <CommandCenter company={company} go={go} />,
    diagnosis: <Diagnosis company={company} focus={focus} go={go} />,
    optimizer: <Optimizer company={company} />,
    profile: <Profile company={company} />,
    whatif: <WhatIf company={company} preset={company === 'fashion' ? preset : null} />,
    history: <History company={company} />,
  }[page]
  return (
    <div className="shell">
      <aside className="side">
        <div className="brand"><div className="brand-mark">₹</div><div><b>AegisOne</b><span>Autonomous Marketing CFO</span></div></div>
        {NAV.map(([k, label, icon], i) => (
          <div key={k}>
            {i === 1 && <div className="nav-sep" />}
            <button className="nav-btn" aria-current={page === k ? 'page' : undefined} onClick={() => go(k)}>
              <span style={{ width: 18, textAlign: 'center' }}>{icon}</span>{label}
              {k === 'diagnosis' && diag.data && <span className="badge">{diag.data.anomaly_count}</span>}
            </button>
          </div>
        ))}
        <div className="side-foot">Synthetic data · no live ad accounts.<br />DataQuest 3.0</div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div><h1>{title}</h1><div className="sub">{sub}</div></div>
          <div className="spacer" />
          {page !== 'demo' && comps.data && (
            <div className="seg" role="group" aria-label="Company">
              {comps.data.map((c) => <button key={c.company_id} aria-pressed={company === c.company_id} onClick={() => { setCompany(c.company_id); setFocus(null) }}>{c.name}</button>)}
            </div>
          )}
        </header>
        <div key={page + (page === 'demo' ? '' : company)}>{view}</div>
      </main>
    </div>
  )
}
