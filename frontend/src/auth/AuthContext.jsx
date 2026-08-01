import { createContext, useContext, useCallback, useEffect, useState } from 'react'
import { getMe, login as apiLogin, logout as apiLogout, setUnauthorizedHandler } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const clearUser = useCallback(() => setUser(null), [])

  useEffect(() => {
    setUnauthorizedHandler(clearUser)
    getMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [clearUser])

  const login = async (email, password) => {
    const loggedInUser = await apiLogin(email, password)
    setUser(loggedInUser)
    return loggedInUser
  }

  const logout = async () => {
    try {
      await apiLogout()
    } finally {
      setUser(null)
    }
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, setUser }}>{children}</AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
