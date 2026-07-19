import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext.jsx'

export default function UserBadge() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  if (!user) return null

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex items-center gap-2 text-sm shrink-0">
      <span className="text-gray-500">
        {user.email} <span className="text-gray-400">({user.role})</span>
      </span>
      <button onClick={handleLogout} className="text-indigo-600 hover:underline font-medium">
        Log out
      </button>
    </div>
  )
}
