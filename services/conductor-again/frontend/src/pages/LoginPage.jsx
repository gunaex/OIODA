import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { Zap, LogIn, Eye, EyeOff } from 'lucide-react';
import { toast } from 'sonner';
import { login as apiLogin } from '../api/client';
import { useAuth } from '../auth/AuthContext';

export default function LoginPage() {
  const { user, setUser } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);

  if (user) return <Navigate to="/" replace />;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await apiLogin(email, password);
      const { getMe } = await import('../api/client');
      const u = await getMe();
      setUser(u);
      toast.success('Welcome back!');
    } catch (err) {
      const msg = err.response?.data?.detail || 'Login failed';
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex bg-gray-50">
      {/* Left — Brand Panel */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-amber-500 via-amber-600 to-orange-700 relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_70%_30%,rgba(255,255,255,0.15)_0%,transparent_60%)]" />
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-20 left-12 w-72 h-72 rounded-full bg-white blur-3xl" />
          <div className="absolute bottom-12 right-12 w-96 h-96 rounded-full bg-amber-300 blur-3xl" />
        </div>
        <div className="relative flex flex-col justify-center px-16 text-white">
          <div className="flex items-center gap-3 mb-8">
            <div className="w-12 h-12 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <Zap size={28} className="text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">Conductor Again</h1>
              <p className="text-amber-100 text-sm">Project Control Plane</p>
            </div>
          </div>
          <h2 className="text-3xl font-bold leading-tight mb-4">
            Orchestrate Projects.<br />Govern AI Capabilities.
          </h2>
          <p className="text-amber-100 text-lg leading-relaxed max-w-md">
            The central control plane for the Again Platform — connecting Vision,
            Requirements, Skills, and AI Resources across your entire delivery ecosystem.
          </p>
          <div className="mt-12 flex gap-8 text-amber-100/80 text-sm">
            <div>
              <div className="text-2xl font-bold text-white">↔</div>
              <div className="mt-1">Cross-App Traceability</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-white">⚡</div>
              <div className="mt-1">Skill Distribution</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-white">🧠</div>
              <div className="mt-1">AI Governance</div>
            </div>
          </div>
        </div>
      </div>

      {/* Right — Login Form */}
      <div className="flex-1 flex items-center justify-center px-6">
        <div className="w-full max-w-sm">
          {/* Mobile brand */}
          <div className="lg:hidden flex items-center gap-3 mb-10 justify-center">
            <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center">
              <Zap size={22} className="text-amber-600" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">Conductor Again</h1>
            </div>
          </div>

          <div className="mb-8">
            <h2 className="text-2xl font-bold text-gray-900">Sign in</h2>
            <p className="mt-1 text-sm text-gray-500">Enter your credentials to continue</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1.5">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-2.5 text-sm border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 transition disabled:bg-gray-50"
                placeholder="admin@conductoragain.local"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPw ? 'text' : 'password'}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-4 py-2.5 text-sm border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 transition pr-10 disabled:bg-gray-50"
                  placeholder="Enter your password"
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 p-1"
                >
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-amber-600 text-white text-sm font-medium rounded-lg hover:bg-amber-700 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 transition disabled:opacity-50"
            >
              {loading ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <LogIn size={16} />
              )}
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <p className="mt-8 text-center text-xs text-gray-400">
            Conductor Again · v0.1.0 · Again Platform
          </p>
        </div>
      </div>
    </div>
  );
}
