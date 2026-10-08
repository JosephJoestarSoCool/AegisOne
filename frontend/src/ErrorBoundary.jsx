import { Component } from 'react'

/** Last line of defence: if a page throws while rendering, show a readable message instead of a blank screen. */
export default class ErrorBoundary extends Component {
  state = { failed: false }

  static getDerivedStateFromError() { return { failed: true } }

  componentDidCatch(error) { console.error('UI error:', error) }   // detail stays in the console, never in the UI

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div className="page" style={{ paddingTop: 80 }}>
        <div className="err" role="alert">
          <p style={{ margin: 0 }}>Something went wrong while showing this page. Your data was not changed.</p>
          <button className="btn small" style={{ marginTop: 10 }} onClick={() => window.location.reload()}>Reload</button>
        </div>
      </div>
    )
  }
}
