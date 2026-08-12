import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link, Outlet, useLocation } from 'react-router-dom';
import { LayoutDashboard, BookOpen, Shield, Zap, Network, Gavel, FileText, FolderOpen,
  Plus, ArrowRight, Target, Clock, Sparkles, CheckCircle2, Link2,
} from 'lucide-react';
import { toast } from 'sonner';
import { listVisions, listRequirements, createVision } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { DashboardSkeleton } from '../components/PageSkeleton';
import EmptyState from '../components/EmptyState';
import StatusBadge from '../components/StatusBadge';
import ConfirmDialog from '../components/ConfirmDialog';
import UserBadge from '../components/UserBadge';
import AIResourcesPage from './AIResourcesPage';
import SkillsPage from './SkillsPage';
import DeliberationPage from './DeliberationPage';
import IntakePage from './IntakePage';
import RequirementsPage from './RequirementsPage';
import VisionPage from './VisionPage';
import IntegrationPage from './IntegrationPage';

const tabs = [
  { to: '', end: true, label: 'Dashboard', icon: LayoutDashboard },
  { to: '/vision', label: 'Vision', icon: BookOpen },
  { to: '/requirements', label: 'Requirements', icon: Shield },
  { to: '/skills', label: 'Skills', icon: Zap },
  { to: '/ai-resources', label: 'AI Resources', icon: Network },
  { to: '/deliberation', label: 'Deliberation', icon: Gavel },
  { to: '/intake', label: 'Intake', icon: FileText },
  { to: '/integration', label: 'Integration', icon: Link2 },
];

export default function ProjectDashboard() {
  const { slug } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [visions, setVisions] = useState([]);
  const [requirements, setRequirements] = useState([]);
  const [activeTab, setActiveTab] = useState('dashboard');

  // Quick-add vision
  const [showVisionInput, setShowVisionInput] = useState(false);
  const [visionContent, setVisionContent] = useState('');
  const [savingVision, setSavingVision] = useState(false);

  // Live counts from platform APIs
  const [skillCount, setSkillCount] = useState(0);
  const [aiResourceCount, setAiResourceCount] = useState(0);
  const [aiAvailableCount, setAiAvailableCount] = useState(0);

  // Golden Flow
  const [goldenFlowRunning, setGoldenFlowRunning] = useState(false);
  const [goldenFlowResult, setGoldenFlowResult] = useState(null);

  useEffect(() => {
    Promise.all([
      listVisions(slug).catch(() => []),
      listRequirements(slug).catch(() => []),
      fetch('/api/skills', { credentials: 'include' }).then(r => r.json()).catch(() => []),
      fetch('/api/ai/pool-summary', { credentials: 'include' }).then(r => r.json()).catch(() => ({})),
    ]).then(([v, r, skills, pool]) => {
      setVisions(v);
      setRequirements(r);
      setSkillCount(Array.isArray(skills) ? skills.length : 0);
      setAiResourceCount(pool.total_resources || 0);
      setAiAvailableCount(pool.available || 0);
    }).catch(() => {
      toast.error('Failed to load project data');
    }).finally(() => setLoading(false));
  }, [slug]);

  const handleGoldenFlow = async () => {
    if (!latestVision) return;
    setGoldenFlowRunning(true);
    setGoldenFlowResult(null);
    try {
      const res = await fetch(`/api/${slug}/golden/trigger`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ vision: latestVision.content }),
      });
      const data = await res.json();
      setGoldenFlowResult(data);
      toast.success('Golden Flow complete!');
      // Refresh requirements
      const reqs = await listRequirements(slug).catch(() => []);
      setRequirements(reqs);
    } catch (err) {
      toast.error('Golden Flow failed');
    } finally {
      setGoldenFlowRunning(false);
    }
  };

  // Determine active tab from URL
  useEffect(() => {
    const path = location.pathname.replace(`/${slug}`, '') || '/';
    if (path === '/' || path === '') setActiveTab('dashboard');
    else if (path.startsWith('/vision')) setActiveTab('vision');
    else if (path.startsWith('/requirements')) setActiveTab('requirements');
    else if (path.startsWith('/skills')) setActiveTab('skills');
    else if (path.startsWith('/ai-resources')) setActiveTab('ai-resources');
    else if (path.startsWith('/deliberation')) setActiveTab('deliberation');
    else if (path.startsWith('/intake')) setActiveTab('intake');
    else if (path.startsWith('/integration')) setActiveTab('integration');
  }, [location.pathname, slug]);

  const handleSaveVision = async (e) => {
    e.preventDefault();
    if (!visionContent.trim()) return;
    setSavingVision(true);
    try {
      const v = await createVision(slug, visionContent.trim());
      setVisions((prev) => [v, ...prev]);
      toast.success('Vision saved');
      setVisionContent('');
      setShowVisionInput(false);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save vision');
    } finally {
      setSavingVision(false);
    }
  };

  if (loading) return <DashboardSkeleton />;

  const latestVision = visions[0];
  const approvedReqs = requirements.filter((r) => r.baseline_approved).length;
  const totalReqs = requirements.length;

  const basePath = `/${slug}`;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* ── Header ────────────────────────────────────── */}
      <header className="sticky top-0 z-40 bg-white/85 backdrop-blur-md border-b border-gray-200">
        <div className="px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14">
            <div className="flex items-center gap-3 min-w-0">
              <Link to="/" className="p-1.5 text-gray-400 hover:text-amber-600 hover:bg-amber-50 rounded-lg transition-colors">
                <FolderOpen size={18} />
              </Link>
              <div className="w-7 h-7 rounded-lg bg-amber-100 flex items-center justify-center flex-shrink-0">
                <Zap size={15} className="text-amber-600" />
              </div>
              <h1 className="text-sm font-semibold text-gray-900 truncate">{slug}</h1>
            </div>
            <UserBadge user={user} />
          </div>

          {/* Tabs */}
          <nav className="flex gap-0 -mb-px overflow-x-auto">
            {tabs.map(({ to, end, label, icon: Icon }) => {
              const isActive = to === ''
                ? (activeTab === 'dashboard')
                : activeTab === to.replace('/', '');
              return (
                <Link
                  key={to}
                  to={`${basePath}${to}`}
                  className={`flex items-center gap-1.5 px-3 sm:px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                    isActive
                      ? 'border-amber-600 text-amber-700'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <Icon size={15} />
                  <span className="hidden sm:inline">{label}</span>
                </Link>
              );
            })}
          </nav>
        </div>
      </header>

      {/* ── Dashboard Content ─────────────────────────── */}
      {activeTab === 'dashboard' && (
        <div className="page-shell py-6 max-w-6xl mx-auto space-y-6">
          {/* Stat cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white border border-gray-200 rounded-xl p-5 card-premium">
              <div className="flex items-center gap-2 text-sm text-gray-500 mb-2">
                <Target size={16} className="text-amber-500" />
                Vision Revisions
              </div>
              <div className="text-2xl font-bold text-gray-900">{visions.length}</div>
              <div className="text-xs text-gray-400 mt-1">
                {latestVision ? `Latest: Rev ${latestVision.revision}` : 'No vision yet'}
              </div>
            </div>

            <div className="bg-white border border-gray-200 rounded-xl p-5 card-premium">
              <div className="flex items-center gap-2 text-sm text-gray-500 mb-2">
                <Shield size={16} className="text-amber-500" />
                Requirements
              </div>
              <div className="text-2xl font-bold text-gray-900">{totalReqs}</div>
              <div className="text-xs text-gray-400 mt-1">{approvedReqs} approved</div>
            </div>

            <div className="bg-white border border-gray-200 rounded-xl p-5 card-premium">
              <div className="flex items-center gap-2 text-sm text-gray-500 mb-2">
                <Zap size={16} className="text-amber-500" />
                Skills
              </div>
              <div className="text-2xl font-bold text-gray-900">{skillCount}</div>
              <div className="text-xs text-gray-400 mt-1">Governed skills</div>
            </div>

            <div className="bg-white border border-gray-200 rounded-xl p-5 card-premium">
              <div className="flex items-center gap-2 text-sm text-gray-500 mb-2">
                <Network size={16} className="text-amber-500" />
                AI Resources
              </div>
              <div className="text-2xl font-bold text-gray-900">{aiResourceCount}</div>
              <div className="text-xs text-gray-400 mt-1">{aiAvailableCount} available</div>
            </div>
          </div>

          {/* Vision Preview */}
          <div className="bg-white border border-gray-200 rounded-xl p-6 card-premium">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <BookOpen size={20} className="text-amber-600" />
                Business Vision
              </h3>
              <button
                onClick={() => setShowVisionInput(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-amber-700 bg-amber-50 rounded-lg hover:bg-amber-100 transition"
              >
                <Plus size={14} />
                {latestVision ? 'New Revision' : 'Add Vision'}
              </button>
            </div>

            {showVisionInput && (
              <form onSubmit={handleSaveVision} className="mb-4 p-4 bg-amber-50/50 rounded-lg border border-amber-200">
                <textarea
                  value={visionContent}
                  onChange={(e) => setVisionContent(e.target.value)}
                  rows={4}
                  className="w-full px-3 py-2 text-sm border border-amber-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-amber-500 transition resize-none"
                  placeholder="Describe the business vision for this project…"
                  autoFocus
                />
                <div className="flex justify-end gap-2 mt-3">
                  <button
                    type="button"
                    onClick={() => { setShowVisionInput(false); setVisionContent(''); }}
                    className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:text-gray-900 transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={savingVision || !visionContent.trim()}
                    className="px-3 py-1.5 text-xs font-medium text-white bg-amber-600 rounded-lg hover:bg-amber-700 disabled:opacity-50 transition flex items-center gap-1.5"
                  >
                    {savingVision && <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />}
                    Save Vision
                  </button>
                </div>
              </form>
            )}

            {latestVision ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-xs text-gray-400">
                  <Clock size={12} />
                  Revision {latestVision.revision} · {new Date(latestVision.created_at).toLocaleDateString()}
                  <span className="text-gray-300">·</span>
                  <span>{latestVision.created_by}</span>
                </div>
                <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                  {latestVision.content}
                </p>
              </div>
            ) : (
              <EmptyState
                icon={BookOpen}
                title="No vision defined"
                description="Start by defining the business vision for this project."
              />
            )}
          </div>

          {/* Golden Flow */}
          <div className="bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-xl p-5 card-premium">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center">
                  <Sparkles size={20} className="text-amber-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">Golden Flow</h3>
                  <p className="text-xs text-gray-500">One-click: Vision → Decompose → Analyze → Deliberate</p>
                </div>
              </div>
              <button
                onClick={handleGoldenFlow}
                disabled={goldenFlowRunning || !latestVision}
                className="inline-flex items-center gap-1.5 px-4 py-2 bg-amber-600 text-white text-sm font-medium rounded-lg hover:bg-amber-700 disabled:opacity-50 transition"
                title={!latestVision ? 'Add a Vision first' : 'Run the golden flow'}
              >
                {goldenFlowRunning ? (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <Sparkles size={16} />
                )}
                {goldenFlowRunning ? 'Running...' : 'Run Golden Flow'}
              </button>
            </div>
            {goldenFlowResult && (
              <div className="mt-3 p-3 bg-white rounded-lg border border-amber-100">
                <div className="text-sm font-medium text-gray-900">{goldenFlowResult.summary}</div>
                <div className="flex flex-wrap gap-3 mt-1.5 text-xs text-gray-500">
                  {goldenFlowResult.steps?.map((s, i) => (
                    <span key={i} className="flex items-center gap-1">
                      <CheckCircle2 size={12} className="text-emerald-500" /> {s.step}: {s.count || s.revision || s.level || s.recommendation}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Requirements Preview */}
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden card-premium">
            <div className="p-6 border-b border-gray-100 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <Shield size={20} className="text-amber-600" />
                Requirements
              </h3>
              <Link
                to={`${basePath}/requirements`}
                className="text-xs text-amber-600 hover:text-amber-700 font-medium flex items-center gap-1"
              >
                View all <ArrowRight size={12} />
              </Link>
            </div>
            {requirements.length === 0 ? (
              <div className="p-6">
                <EmptyState
                  icon={Shield}
                  title="No requirements yet"
                  description="Requirements will appear here once created."
                />
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {requirements.slice(0, 5).map((req) => (
                  <div key={req.id} className="px-6 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <code className="text-xs font-mono text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded">{req.code}</code>
                        <span className="text-sm font-medium text-gray-900 truncate">{req.title}</span>
                      </div>
                    </div>
                    <StatusBadge status={req.status} />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Placeholder tabs */}
      {activeTab === 'vision' && <VisionPage slug={slug} />}

      {activeTab === 'requirements' && <RequirementsPage slug={slug} />}

      {activeTab === 'skills' && <SkillsPage />}

      {activeTab === 'ai-resources' && <AIResourcesPage />}

      {activeTab === 'deliberation' && <DeliberationPage />}

      {activeTab === 'intake' && <IntakePage slug={slug} />}
      {activeTab === 'integration' && <IntegrationPage slug={slug} />}
    </div>
  );
}
