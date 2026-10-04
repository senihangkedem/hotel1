import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function LoginPage() {
  const { user, login, loading } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [form, setForm] = useState({ username: '', password: '' })
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (loading) {
    return <div className="page-shell">Loading...</div>
  }

  const destination = location.state?.from || '/dashboard'

  if (user) {
    return <Navigate to={destination} replace />
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')

    if (!form.username.trim() || !form.password.trim()) {
      setError('Please enter both username and password.')
      return
    }

    try {
      setSubmitting(true)
      await login(form.username, form.password)
      navigate(destination, { replace: true })
    } catch (err) {
      const message = err.response?.data?.detail || 'Login failed. Please check your username and password.'
      setError(message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="page-shell auth-shell">
      <div className="auth-card">
        <h1>Restaurant SaaS</h1>
        <h2>Login</h2>

        <form onSubmit={handleSubmit} className="auth-form">
          <label>
            <span>Username</span>
            <input
              type="text"
              value={form.username}
              onChange={(event) => setForm({ ...form, username: event.target.value })}
              autoComplete="username"
            />
          </label>

          <label>
            <span>Password</span>
            <input
              type="password"
              value={form.password}
              onChange={(event) => setForm({ ...form, password: event.target.value })}
              autoComplete="current-password"
            />
          </label>

          {error && <div className="form-error">{error}</div>}

          <button type="submit" disabled={submitting}>
            {submitting ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}
