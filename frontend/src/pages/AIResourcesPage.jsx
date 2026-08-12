import { useEffect, useState } from 'react';
import {
  Network, Server, Cpu, Activity, Zap, Shield, AlertTriangle,
  CheckCircle2, XCircle, Clock, Plus, RefreshCw, Eye, EyeOff,
  Trash2, Settings2, Radio, Wifi, WifiOff,
} from 'lucide-react';
import ConfirmDialog from '../components/ConfirmDialog';
import { toast } from 'sonner';
import { CardSkeleton } from '../components/PageSkeleton';
import EmptyState from '../components/EmptyState';
import StatusBadge from '../components/StatusBadge';

const API = '/api/ai';

async function fetchJSON(url, options = {}) {
  const res = await fetch(url, { credentials: 'include', ...options });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const clone = res.clone();
      msg = (await clone.json()).detail || msg;
    } catch {
      try { msg = (await res.clone().text()).slice(0, 200) || msg; } catch { /* use status */ }
    }
    throw new Error(msg);
  }
  return res.json();
}

export default function AIResourcesPage() {
  // Data
  const [loading, setLoading] = useState(true);
  const [providers, setProviders] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [models, setModels] = useState([]);
  const [resources, setResources] = useState([]);
  const [poolSummary, setPoolSummary] = useState(null);

  // UI state
  const [activeTab, setActiveTab] = useState('overview');
  const [showAddAccount, setShowAddAccount] = useState(false);
  const [showApiKey, setShowApiKey] = useState({});
  const [testingId, setTestingId] = useState(null);
  const [healthCheckId, setHealthCheckId] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);  // { id, name }
  const [deleting, setDeleting] = useState(false);

  // Add account form
  const [newAccount, setNewAccount] = useState({
    provider_id: '', name: '', api_key: '', api_base_url: '',
  });

  const loadAll = async () => {
    try {
      const [p, a, m, r, s] = await Promise.all([
        fetchJSON(`${API}/providers`),
        fetchJSON(`${API}/accounts`),
        fetchJSON(`${API}/models`),
        fetchJSON(`${API}/resources`),
        fetchJSON(`${API}/pool-summary`),
      ]);
      setProviders(p);
      setAccounts(a);
      setModels(m);
      setResources(r);
      setPoolSummary(s);
    } catch (e) {
      toast.error('Failed to load AI resources');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAll(); }, []);

  const handleAddAccount = async (e) => {
    e.preventDefault();
    try {
      await fetchJSON(`${API}/accounts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newAccount),
      });
      toast.success('Account added');
      setShowAddAccount(false);
      setNewAccount({ provider_id: '', name: '', api_key: '', api_base_url: '' });
      loadAll();
    } catch (e) {
      toast.error(e.message);
    }
  };

  const handleHealthCheck = async (accountId) => {
    setHealthCheckId(accountId);
    try {
      const result = await fetchJSON(`${API}/accounts/${accountId}/health-check`, { method: 'POST' });
      toast[result.ok ? 'success' : 'error'](result.ok ? 'Connection OK' : result.message);
      loadAll();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setHealthCheckId(null);
    }
  };

  const handleDeleteAccount = async () => {
    if (!confirmDelete) return;
    setDeleting(true);
    try {
      await fetchJSON(`${API}/accounts/${confirmDelete.id}`, { method: 'DELETE' });
      toast.success(`Deleted: ${confirmDelete.name}`);
      setConfirmDelete(null);
      loadAll();
    } catch (e) {
      toast.error(e.message);
    } finally { setDeleting(false); }
  };

  const handleTest = async (resourceId) => {
    setTestingId(resourceId);
    try {
      const result = await fetchJSON(`${API}/resources/${resourceId}/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: 'Say hello and introduce yourself in one sentence.' }),
      });
      if (result.ok) {
        toast.success(`Response: "${result.response?.slice(0, 80)}..."`);
      } else {
        toast.error(result.error || 'Test failed');
      }
    } catch (e) {
      toast.error(e.message);
    } finally {
      setTestingId(null);
    }
  };

  if (loading) return <CardSkeleton count={6} />;

  const getProviderName = (id) => providers.find((p) => p.id === id)?.name || 'Unknown';
  const getProviderCode = (id) => providers.find((p) => p.id === id)?.code || 'unknown';

  const providerAccounts = (providerId) => accounts.filter((a) => a.provider_id === providerId);

  const healthIcon = (state) => {
    switch (state) {
      case 'AVAILABLE': return <CheckCircle2 size={14} className="text-emerald-500" />;
      case 'BUSY': return <Clock size={14} className="text-amber-500" />;
      case 'DEGRADED': return <AlertTriangle size={14} className="text-amber-500" />;
      case 'RATE_LIMITED': return <Activity size={14} className="text-orange-500" />;
      case 'OFFLINE': case 'AUTH_EXPIRED': case 'SUSPENDED': case 'REVOKED':
        return <XCircle size={14} className="text-red-500" />;
      case 'MANUAL_ONLY': return <WifiOff size={14} className="text-gray-400" />;
      default: return <Wifi size={14} className="text-gray-400" />;
    }
  };

  return (
    <div className="page-shell py-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <Network size={22} className="text-amber-600" />
            AI Resource Pool
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Governed registry of all approved AI providers, accounts, models, and routable resources.
          </p>
        </div>
        <button
          onClick={() => setShowAddAccount(true)}
          className="inline-flex items-center gap-1.5 px-3 py-2 bg-amber-600 text-white text-sm font-medium rounded-lg hover:bg-amber-700 transition focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2"
        >
          <Plus size={16} />
          Add Account
        </button>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit">
        {[
          { key: 'overview', label: 'Overview', icon: Network },
          { key: 'providers', label: 'Providers', icon: Server },
          { key: 'accounts', label: 'Accounts', icon: Settings2 },
          { key: 'models', label: 'Models', icon: Cpu },
          { key: 'resources', label: 'Resources', icon: Zap },
        ].map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md transition ${
              activeTab === key
                ? 'bg-white text-amber-700 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      {/* ════════════════ OVERVIEW ════════════════ */}
      {activeTab === 'overview' && poolSummary && (
        <div className="space-y-6">
          {/* Stat cards */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {[
              { label: 'Providers', value: poolSummary.provider_count, icon: Server, color: 'text-purple-500', bg: 'bg-purple-50' },
              { label: 'Accounts', value: poolSummary.account_count, icon: Settings2, color: 'text-blue-500', bg: 'bg-blue-50' },
              { label: 'Models', value: poolSummary.model_count, icon: Cpu, color: 'text-emerald-500', bg: 'bg-emerald-50' },
              { label: 'Available', value: poolSummary.available, icon: CheckCircle2, color: 'text-emerald-600', bg: 'bg-emerald-50' },
              { label: 'Degraded', value: poolSummary.degraded, icon: AlertTriangle, color: 'text-amber-600', bg: 'bg-amber-50' },
              { label: 'Offline', value: poolSummary.offline, icon: XCircle, color: 'text-red-500', bg: 'bg-red-50' },
            ].map(({ label, value, icon: Icon, color, bg }) => (
              <div key={label} className="bg-white border border-gray-200 rounded-xl p-4 card-premium">
                <div className={`w-8 h-8 rounded-lg ${bg} flex items-center justify-center mb-2`}>
                  <Icon size={16} className={color} />
                </div>
                <div className="text-2xl font-bold text-gray-900">{value}</div>
                <div className="text-xs text-gray-500">{label}</div>
              </div>
            ))}
          </div>

          {/* Provider cards */}
          <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <Server size={18} className="text-amber-600" /> Providers
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {providers.map((p) => {
              const accts = providerAccounts(p.id);
              const enabled = accts.filter((a) => a.enabled).length;
              const healthy = accts.filter((a) => a.health_state === 'AVAILABLE').length;
              return (
                <div key={p.id} className="bg-white border border-gray-200 rounded-xl p-5 card-premium">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg bg-amber-50 flex items-center justify-center text-sm font-bold text-amber-600">
                        {p.name[0]}
                      </div>
                      <div>
                        <div className="font-semibold text-gray-900 text-sm">{p.name}</div>
                        <code className="text-xs text-gray-400">{p.code}</code>
                      </div>
                    </div>
                    {p.enabled ? (
                      <CheckCircle2 size={16} className="text-emerald-500" />
                    ) : (
                      <XCircle size={16} className="text-red-400" />
                    )}
                  </div>
                  {p.description && (
                    <p className="text-xs text-gray-500 line-clamp-2 mb-3">{p.description}</p>
                  )}
                  <div className="flex gap-3 text-xs">
                    <span className="text-gray-500">{accts.length} account{accts.length !== 1 ? 's' : ''}</span>
                    {enabled > 0 && <span className="text-emerald-600">{healthy} healthy</span>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ════════════════ PROVIDERS ════════════════ */}
      {activeTab === 'providers' && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="divide-y divide-gray-100">
            {providers.map((p) => (
              <div key={p.id} className="px-5 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-amber-50 flex items-center justify-center text-sm font-bold text-amber-600">
                    {p.name[0]}
                  </div>
                  <div>
                    <div className="font-medium text-gray-900 text-sm">{p.name}</div>
                    <div className="text-xs text-gray-400">{p.website || p.code}</div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-400">{providerAccounts(p.id).length} accounts</span>
                  <StatusBadge status={p.enabled ? 'active' : 'archived'} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ════════════════ ACCOUNTS ════════════════ */}
      {activeTab === 'accounts' && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          {accounts.length === 0 ? (
            <div className="p-6">
              <EmptyState icon={Settings2} title="No accounts yet" description="Add your first AI provider account to get started." />
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {accounts.map((a) => (
                <div key={a.id} className="px-5 py-4 hover:bg-gray-50 transition-colors">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 min-w-0">
                      {healthIcon(a.health_state)}
                      <div className="min-w-0">
                        <div className="font-medium text-gray-900 text-sm truncate">{a.name}</div>
                        <div className="flex items-center gap-2 text-xs text-gray-400 mt-0.5">
                          <span>{getProviderName(a.provider_id)}</span>
                          <span>·</span>
                          <span>{a.access_mode}</span>
                          {a.api_key_last4 && <><span>·</span><span>Key: ****{a.api_key_last4}</span></>}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${
                        a.connector_status === 'SUPPORTED' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                        a.connector_status === 'PARTIALLY_SUPPORTED' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                        'bg-gray-100 text-gray-600 border-gray-200'
                      }`}>
                        {a.connector_status.replace('_', ' ')}
                      </span>
                      <button
                        onClick={() => handleHealthCheck(a.id)}
                        disabled={healthCheckId === a.id}
                        className="p-1.5 text-gray-400 hover:text-amber-600 hover:bg-amber-50 rounded-lg transition-colors"
                        title="Health check"
                      >
                        <RefreshCw size={14} className={healthCheckId === a.id ? 'animate-spin' : ''} />
                      </button>
                      <button
                        onClick={() => setConfirmDelete({ id: a.id, name: a.name })}
                        className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                        title="Delete account"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                  {a.total_requests > 0 && (
                    <div className="mt-2 flex gap-4 text-xs text-gray-400">
                      <span>{a.total_requests.toLocaleString()} requests</span>
                      <span>{(a.total_cost_usd || 0).toFixed(4)} USD</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ════════════════ MODELS ════════════════ */}
      {activeTab === 'models' && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          {models.length === 0 ? (
            <div className="p-6">
              <EmptyState icon={Cpu} title="No models registered" description="Models are auto-registered when you add an account." />
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {models.map((m) => (
                <div key={m.id} className="px-5 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-purple-50 flex items-center justify-center">
                      <Cpu size={16} className="text-purple-500" />
                    </div>
                    <div>
                      <div className="font-medium text-gray-900 text-sm">{m.display_name}</div>
                      <code className="text-xs text-gray-400">{m.model_id}</code>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap justify-end">
                    {(m.capabilities || []).slice(0, 2).map((c) => (
                      <span key={c} className="inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-100 text-gray-600">
                        {c}
                      </span>
                    ))}
                    {(m.capabilities || []).length > 2 && (
                      <span className="text-[10px] text-gray-400">+{m.capabilities.length - 2}</span>
                    )}
                    <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium ${
                      m.quality_class === 'premium' ? 'bg-amber-100 text-amber-700' :
                      m.quality_class === 'balanced' ? 'bg-blue-100 text-blue-700' :
                      'bg-gray-100 text-gray-600'
                    }`}>
                      {m.quality_class}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ════════════════ RESOURCES ════════════════ */}
      {activeTab === 'resources' && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          {resources.length === 0 ? (
            <div className="p-6">
              <EmptyState icon={Zap} title="No routable resources" description="Resources are created automatically when you add accounts." />
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {resources.map((r) => (
                <div key={r.id} className="px-5 py-4 hover:bg-gray-50 transition-colors">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 min-w-0">
                      {healthIcon(r.health_state)}
                      <div className="min-w-0">
                        <div className="font-medium text-gray-900 text-sm">{r.display_name}</div>
                        <div className="text-xs text-gray-400">
                          Priority {r.base_priority} · Concurrency {r.current_concurrency}/{r.max_concurrency}
                          {r.success_rate < 1 && ` · ${(r.success_rate * 100).toFixed(0)}% success`}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {(r.entitlements || []).slice(0, 3).map((e) => (
                        <span key={e} className="inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-50 text-amber-700">
                          {e}
                        </span>
                      ))}
                      <button
                        onClick={() => handleTest(r.id)}
                        disabled={testingId === r.id || r.health_state === 'OFFLINE'}
                        className="ml-2 px-2.5 py-1 text-xs font-medium text-amber-700 bg-amber-50 rounded-md hover:bg-amber-100 disabled:opacity-50 transition flex items-center gap-1"
                      >
                        <Zap size={12} className={testingId === r.id ? 'animate-pulse' : ''} />
                        {testingId === r.id ? '...' : 'Test'}
                      </button>
                    </div>
                  </div>
                  {(r.allowed_data_classifications || []).length > 0 && (
                    <div className="mt-1.5 flex gap-1">
                      {r.allowed_data_classifications.map((c) => (
                        <span key={c} className="text-[10px] text-gray-400">[{c}]</span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ════════════════ ADD ACCOUNT MODAL ════════════════ */}
      {showAddAccount && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setShowAddAccount(false)} />
          <div className="relative bg-white rounded-xl shadow-2xl max-w-lg w-full mx-4 p-6 z-10 max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-semibold text-gray-900 mb-1">Add AI Account</h2>
            <p className="text-sm text-gray-500 mb-5">Register a new API account, local runtime, or manual-handoff resource.</p>
            <form onSubmit={handleAddAccount} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Provider</label>
                <select
                  required
                  value={newAccount.provider_id}
                  onChange={(e) => setNewAccount({ ...newAccount, provider_id: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 transition bg-white"
                >
                  <option value="">Select provider...</option>
                  {providers.filter((p) => p.enabled).map((p) => (
                    <option key={p.id} value={p.id}>{p.name} ({p.code})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Account Name</label>
                <input
                  type="text"
                  required
                  value={newAccount.name}
                  onChange={(e) => setNewAccount({ ...newAccount, name: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 transition"
                  placeholder="e.g. DeepSeek Company Account"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">API Base URL</label>
                <input
                  type="text"
                  value={newAccount.api_base_url}
                  onChange={(e) => setNewAccount({ ...newAccount, api_base_url: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 transition font-mono"
                  placeholder="https://api.deepseek.com"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">API Key</label>
                <div className="relative">
                  <input
                    type={showApiKey['new'] ? 'text' : 'password'}
                    value={newAccount.api_key}
                    onChange={(e) => setNewAccount({ ...newAccount, api_key: e.target.value })}
                    className="w-full px-3 py-2 pr-10 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 transition font-mono"
                    placeholder="sk-..."
                  />
                  <button
                    type="button"
                    onClick={() => setShowApiKey({ ...showApiKey, new: !showApiKey['new'] })}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showApiKey['new'] ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
                <p className="text-xs text-gray-400 mt-1">Encrypted at rest. Never returned after creation.</p>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddAccount(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-sm font-medium text-white bg-amber-600 rounded-lg hover:bg-amber-700 transition flex items-center gap-1.5"
                >
                  <Plus size={14} />
                  Add Account
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ════════════════ DELETE CONFIRM ════════════════ */}
      <ConfirmDialog
        open={!!confirmDelete}
        title="Delete AI Account"
        message={`Are you sure you want to delete "${confirmDelete?.name}"? This will cascade-delete all associated runtimes, models, and resources. This action cannot be undone.`}
        confirmLabel={deleting ? 'Deleting...' : 'Delete'}
        danger
        loading={deleting}
        onConfirm={handleDeleteAccount}
        onCancel={() => setConfirmDelete(null)}
      />
    </div>
  );
}
