import { Component } from 'react'

export default class AppErrorBoundary extends Component {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error, info) {
    if (import.meta.env.DEV) {
      console.error('Application render failed', error, info.componentStack)
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="app-error-boundary" role="alert">
          <h1>The application could not be displayed.</h1>
          <p>Reload the page to try again. Your account data has not been changed.</p>
          <button type="button" onClick={() => window.location.reload()}>
            Reload application
          </button>
        </main>
      )
    }

    return this.props.children
  }
}