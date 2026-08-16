import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext.jsx'
import ForcePasswordChangePage from '../pages/ForcePasswordChangePage.jsx'
import CommandPalette from '../components/CommandPalette.jsx'

export default function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center text-sm text-gray-500">Loading…</div>
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  // Backend rejects every other endpoint with 403 while this is set (see
  // auth.py's _PASSWORD_CHANGE_EXEMPT_PATHS) — this is the UI-side mirror of
  // that gate, not the enforcement itself.
  if (user.must_change_password) {
    return <ForcePasswordChangePage />
  }

  return (
    <>
      {children}
      <CommandPalette />
    </>
  )
}
