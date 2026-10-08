import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/inter'
import '@fontsource-variable/archivo/wdth.css'
import '@fontsource/instrument-serif/400-italic.css'
import './styles.css'
import './lab.css'
import './editorial.css'
import './art.css'
import './impact.css'
import App from './App.jsx'
import ErrorBoundary from './ErrorBoundary.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary><App /></ErrorBoundary>
  </StrictMode>,
)
