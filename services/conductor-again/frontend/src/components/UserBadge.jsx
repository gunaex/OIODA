import { User, LogOut } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { logout as apiLogout } from '../api/client';

const ROLE_COLORS = {
  admin: 'bg-purple-100 text-purple-700',
  conductor: 'bg-amber-100 text-amber-700',
  approver: 'bg-emerald-100 text-emerald-700',
  contributor: 'bg-blue-100 text-blue-700',
  viewer: 'bg-gray-100 text-gray-600',
};

export default function UserBadge({ user }) {
  const navigate = useNavigate();

  if (!user) return null;

  const handleLogout = async () => {
    try {
      await apiLogout();
    } catch {
      // ignore
    }
    navigate('/login');
  };

  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-2">
        <div className="w-7 h-7 rounded-full bg-amber-100 flex items-center justify-center">
          <User size={14} className="text-amber-600" />
        </div>
        <div className="hidden sm:block text-right">
          <div className="text-xs font-medium text-gray-900 leading-tight">
            {user.display_name}
          </div>
          <div className={`text-[10px] font-medium px-1.5 py-px rounded-full inline-block ${ROLE_COLORS[user.role] || ROLE_COLORS.viewer}`}>
            {user.role}
          </div>
        </div>
      </div>
      <button
        onClick={handleLogout}
        className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
        title="Sign out"
      >
        <LogOut size={14} />
      </button>
    </div>
  );
}
