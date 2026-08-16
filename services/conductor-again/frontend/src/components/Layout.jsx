import { useState } from 'react';
import { NavLink, Outlet, useParams } from 'react-router-dom';
import { BookOpen, LayoutDashboard, Network, Shield, Zap, ChevronDown } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import UserBadge from './UserBadge';

const tabs = [
  { to: '', end: true, label: 'Dashboard', icon: LayoutDashboard },
  { to: '/vision', label: 'Vision', icon: BookOpen },
  { to: '/requirements', label: 'Requirements', icon: Shield },
  { to: '/skills', label: 'Skills', icon: Zap },
  { to: '/ai-resources', label: 'AI Resources', icon: Network },
];

export default function Layout() {
  const { slug } = useParams();
  const { user } = useAuth();
  const [error] = useState(null);

  const basePath = `/${slug}`;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* ── Sticky Header ──────────────────────────────── */}
      <header className="sticky top-0 z-40 bg-white/85 backdrop-blur-md border-b border-gray-200">
        <div className="px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14">
            {/* Brand */}
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-amber-100 flex items-center justify-center">
                  <Zap size={18} className="text-amber-600" />
                </div>
                <div>
                  <span className="text-sm font-semibold text-gray-900">Conductor</span>
                  <span className="text-sm font-medium text-amber-600"> Again</span>
                </div>
              </div>
              {slug && (
                <span className="hidden sm:inline text-xs text-gray-400 border-l border-gray-200 pl-3">
                  {slug}
                </span>
              )}
            </div>

            {/* Right */}
            <div className="flex items-center gap-3">
              <NavLink
                to="/"
                className="text-xs text-gray-500 hover:text-amber-600 transition-colors hidden sm:block"
              >
                All Projects
              </NavLink>
              <UserBadge user={user} />
            </div>
          </div>

          {/* Tabs — only inside a project */}
          {slug && (
            <nav className="flex gap-0 -mb-px overflow-x-auto">
              {tabs.map(({ to, end, label, icon: Icon }) => (
                <NavLink
                  key={to}
                  to={`${basePath}${to}`}
                  end={end}
                  className={({ isActive }) =>
                    `flex items-center gap-1.5 px-3 sm:px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                      isActive
                        ? 'border-amber-600 text-amber-700'
                        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                    }`
                  }
                >
                  <Icon size={15} />
                  <span className="hidden sm:inline">{label}</span>
                </NavLink>
              ))}
            </nav>
          )}
        </div>
      </header>

      {/* Error Banner */}
      {error && (
        <div className="bg-red-50 border-b border-red-200 text-red-700 px-4 py-2 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button
            onClick={() => window.location.reload()}
            className="text-red-800 underline text-xs ml-4"
          >
            Retry
          </button>
        </div>
      )}

      {/* Content */}
      <main>
        <Outlet />
      </main>
    </div>
  );
}
