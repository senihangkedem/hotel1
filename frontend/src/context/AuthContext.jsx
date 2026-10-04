/* eslint-disable react-refresh/only-export-components */
/* eslint-disable react-hooks/set-state-in-effect */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import api from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const isAuthenticated = Boolean(user)

  const clearAuth = useCallback(() => {
    localStorage.removeItem('accessToken')
    localStorage.removeItem('refreshToken')
    setUser(null)
  }, [])

  const loadCurrentUser = useCallback(async () => {
    const accessToken = localStorage.getItem('accessToken')
    if (!accessToken) {
      setUser(null)
      setLoading(false)
      return
    }

    try {
      const response = await api.get('/auth/me/')
      setUser(response.data)
    } catch {
      clearAuth()
    } finally {
      setLoading(false)
    }
  }, [clearAuth])

  useEffect(() => {
    void loadCurrentUser()
  }, [loadCurrentUser])

  const login = useCallback(async (username, password) => {
    const response = await api.post('/auth/token/', { username, password })
    const { access, refresh } = response.data

    localStorage.setItem('accessToken', access)
    localStorage.setItem('refreshToken', refresh)

    const userResponse = await api.get('/auth/me/')
    setUser(userResponse.data)
    return userResponse.data
  }, [])

  const logout = useCallback(() => {
    clearAuth()
    window.location.href = '/login'
  }, [clearAuth])

  const refreshUser = useCallback(async () => {
    await loadCurrentUser()
  }, [loadCurrentUser])

  const value = useMemo(
    () => ({ user, isAuthenticated, loading, login, logout, refreshUser }),
    [user, isAuthenticated, loading, login, logout, refreshUser],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)

  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }

  return context
}
