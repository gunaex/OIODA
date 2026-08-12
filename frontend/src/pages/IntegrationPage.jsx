import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Link2, ExternalLink, Activity, CheckCircle2, XCircle, Clock,
  RefreshCw, Send, Eye, Plus, Trash2, Shield, BookOpen,
  ArrowRight, FileText, Server, AlertTriangle,
} from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../auth/AuthContext';
import EmptyState from '../components/EmptyState';
import ConfirmDialog from '../components/ConfirmDialog';

const SERVICE_ICONS = {
  'pm-again': FileText,
  'qa-again': Shield,
  'dev-again': Server,
};

const SERVICE_COLORS = {
  'pm-again': 'indigo',
  'qa-again': 'emerald',
  'dev-again': 'blue',
};

async function fetchJSON(url, options = {}) {
  const res = await fetch(url, { credentials: 'include', ...options });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const clone = res.clone();
      msg = (await clone.json()).detail || msg;
    } catch {
      try { msg = (await res.clone().text()).slice(0, 200) || msg; } catch {}
    }
    throw new Error(msg);
  }
  return res.json();
}

export default function IntegrationPage() {
  const { slug } = useParams();
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [services, setServices] = useState([]);
  const [traceMatrix, setTraceMatrix] = useState(null);
  const [artifactRefs, setArtifactRefs] = useState([]);
  const [traceLinks, setTraceLinks] = useState([]);
  const [view, setView] = useState('services'); // services, trace, refs
  const [checkingHealth, setCheckingHealth] = useState({});
  const [sendingPlan, setSendingPlan] = useState(false);
  const [confirmSend, setConfirmSend] = useState(null);

  useEffect(() => {
    loadAll();
  }, [slug]);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [svc, matrix, refs, links] = await Promise.all([
        fetchJSON('/api/integration/services'),
        fetchJSON(`/api/${slug}/trace/matrix`).catch(() => null),
        fetchJSON(`/api/${slug}/trace/artifact-refs`).catch(() => []),
        fetchJSON(`/api/${slug}/trace/links`).catch(() => []),
      ]);
      setServices(svc);
      setTraceMatrix(matrix);
      setArtifactRefs(Array.isArray(refs) ? refs : []);
      setTraceLinks(Array.isArray(links) ? links : []);
    } catch (err) {
      toast.error('Failed to load integration data');
    } finally {
      setLoading(false);
    }
  };

  const handleHealthCheck = async (code) => {
    setCheckingHealth((prev) => ({ ...prev, [code]: true }));
    try {
      const result = await fetchJSON(`/api/integration/services/${code}/health`, { method: 'POST' });
      toast.success(`${code}: ${result.ok ? 'Online' : result.message || result.status || 'Offline'}`);
    } catch (err) {
      toast.error(`Health check failed: ${err.message}`);
    } finally {
      setCheckingHealth((prev) => ({ ...prev, [code]: false }));
    }
  };

  const handleSendDeliveryPlan = async () => {
    setSendingPlan(true);
    try {
      const result = await fetchJSON(`/api/${slug}/integration/pm/delivery-plan`, { method: 'POST' });
      if (result.ok) {
        toast.success(`Delivery plan sent to PM Again (${result.status_code})`);
      } else {
        toast.error(result.error || 'Failed to send delivery plan');
      }
    } catch (err) {
      toast.error(err.message);
    } finally {
      setSendingPlan(false);
      setConfirmSend(null);
    }
  };

  const statusBadge = (status) => {
    const map = {
      CONNECTED: 'bg-emerald-100 text-emerald-700',
      DEPLOYING: 'bg-blue-100 text-blue-700',
      PENDING_DEPLOYMENT: 'bg-amber-100 text-amber-700',
      PLANNED: 'bg-gray-100 text-gray-500',
      DEGRADED: 'bg-orange-100 text-orange-700',
      DISABLED: 'bg-red-100 text-red-700',
    };
    return map[status] || 'bg-gray-100 text-gray-500';
  };

  const traceRows = traceMatrix?.rows || [];
  const tracedCount = traceRows.filter((r) => r.pm_artifacts?.length || r.qa_artifacts?.length).length;

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto py-6 px-4 space-y-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded w-64" />
          <div className="grid grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => <div key={i} className="h-32 bg-gray-100 rounded-xl" />)}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto py-6 px-4 space-y-6">
      {/* Header + sub-tabs */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <Link2 size={22} className="text-amber-600" />
            Integration & Traceability
          </h2>
          <p className="text-sm text-gray-500 mt-1">Cross-app orchestration with Again Platform siblings</p>
        </div>
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          {[
            { key: 'services', label: 'Services', icon: Server },
            { key: 'trace', label: 'Trace Matrix', icon: Eye },
            { key: 'refs', label: 'References', icon: Link2 },
          ].map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setView(key)}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md transition ${
                view === key ? 'bg-white text-amber-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <Icon size={14} />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Services View ─────────────────────────────── */}
      {view === 'services' && (
        <div className="space-y-4">
          {services.length === 0 ? (
            <EmptyState icon={Server} title="No services registered" description="Sibling Again Platform services will appear here." />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {services.map((svc) => {
                const Icon = SERVICE_ICONS[svc.code] || Server;
                const colorClass = SERVICE_COLORS[svc.code] || 'amber';
                const isChecking = checkingHealth[svc.code];

                return (
                  <div key={svc.code} className="bg-white border border-gray-200 rounded-xl p-5 card-premium">
                    <div className="flex items-start justify-between mb-3">
                      <div className={`w-10 h-10 rounded-lg bg-${colorClass}-100 flex items-center justify-center`}>
                        <Icon size={20} className={`text-${colorClass}-600`} />
                      </div>
                      <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${statusBadge(svc.status)}`}>
                        {svc.status.replace('_', ' ')}
                      </span>
                    </div>
                    <h3 className="font-semibold text-gray-900">{svc.name}</h3>
                    <p className="text-xs text-gray-500 mt-1 mb-3">{svc.description}</p>
                    {svc.base_url && (
                      <a href={svc.base_url} target="_blank" rel="noopener noreferrer"
                        className="text-xs text-amber-600 hover:text-amber-700 flex items-center gap-1 mb-3">
                        <ExternalLink size={11} />
                        {svc.base_url}
                      </a>
                    )}
                    <div className="flex gap-2 mt-auto">
                      <button
                        onClick={() => handleHealthCheck(svc.code)}
                        disabled={isChecking || svc.status === 'PLANNED'}
                        className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-50 rounded-lg hover:bg-gray-100 disabled:opacity-50 transition"
                      >
                        <Activity size={13} className={isChecking ? 'animate-spin' : ''} />
                        {isChecking ? 'Checking...' : 'Health'}
                      </button>
                      {svc.code === 'pm-again' && svc.status === 'CONNECTED' && (
                        <button
                          onClick={() => setConfirmSend(svc)}
                          disabled={sendingPlan}
                          className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-amber-600 rounded-lg hover:bg-amber-700 disabled:opacity-50 transition"
                        >
                          <Send size={13} />
                          Send Plan
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ── Trace Matrix View ─────────────────────────── */}
      {view === 'trace' && (
        <div className="space-y-4">
          {traceMatrix ? (
            <>
              <div className="grid grid-cols-4 gap-4">
                <div className="bg-white border border-gray-200 rounded-xl p-4 card-premium">
                  <div className="text-xs text-gray-500">Requirements</div>
                  <div className="text-2xl font-bold text-gray-900">{traceMatrix.requirements_count}</div>
                </div>
                <div className="bg-white border border-gray-200 rounded-xl p-4 card-premium">
                  <div className="text-xs text-gray-500">Traced</div>
                  <div className="text-2xl font-bold text-emerald-700">{tracedCount}</div>
                </div>
                <div className="bg-white border border-gray-200 rounded-xl p-4 card-premium">
                  <div className="text-xs text-gray-500">Untraced</div>
                  <div className="text-2xl font-bold text-amber-700">{traceMatrix.requirements_count - tracedCount}</div>
                </div>
                <div className="bg-white border border-gray-200 rounded-xl p-4 card-premium">
                  <div className="text-xs text-gray-500">Coverage</div>
                  <div className="text-2xl font-bold text-gray-900">
                    {traceMatrix.requirements_count > 0
                      ? Math.round((tracedCount / traceMatrix.requirements_count) * 100)
                      : 0}%
                  </div>
                </div>
              </div>

              {traceRows.length === 0 ? (
                <EmptyState icon={Eye} title="No trace data" description="Send requirements to PM Again or QA Again to build traceability." />
              ) : (
                <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="text-left px-4 py-3 font-medium text-gray-500">Requirement</th>
                        <th className="text-left px-4 py-3 font-medium text-gray-500">Status</th>
                        <th className="text-left px-4 py-3 font-medium text-gray-500">PM Artifacts</th>
                        <th className="text-left px-4 py-3 font-medium text-gray-500">QA Artifacts</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {traceRows.map((row) => (
                        <tr key={row.requirement_code} className="hover:bg-gray-50">
                          <td className="px-4 py-3">
                            <div className="font-medium text-gray-900">{row.requirement_code}</div>
                            <div className="text-xs text-gray-500 truncate max-w-[200px]">{row.requirement_title}</div>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`px-2 py-0.5 text-xs rounded-full ${
                              row.requirement_status === 'approved' ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-500'
                            }`}>{row.requirement_status}</span>
                          </td>
                          <td className="px-4 py-3">
                            {row.pm_artifacts?.length > 0 ? (
                              <div className="space-y-1">
                                {row.pm_artifacts.map((a) => (
                                  <div key={a.id} className="flex items-center gap-1 text-xs">
                                    <span className="px-1.5 py-0.5 bg-indigo-50 text-indigo-700 rounded">{a.type}</span>
                                    <span className="text-gray-500">{a.id}</span>
                                    <span className={`text-xs ${a.status === 'done' ? 'text-emerald-600' : 'text-amber-600'}`}>
                                      {a.status}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            ) : <span className="text-xs text-gray-300">—</span>}
                          </td>
                          <td className="px-4 py-3">
                            {row.qa_artifacts?.length > 0 ? (
                              <div className="space-y-1">
                                {row.qa_artifacts.map((a) => (
                                  <div key={a.id} className="flex items-center gap-1 text-xs">
                                    <span className="px-1.5 py-0.5 bg-emerald-50 text-emerald-700 rounded">{a.type}</span>
                                    <span className="text-gray-500">{a.id}</span>
                                  </div>
                                ))}
                              </div>
                            ) : <span className="text-xs text-gray-300">—</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          ) : (
            <EmptyState icon={Eye} title="No trace data yet" description="Requirements need to be mapped to sibling artifacts." />
          )}
        </div>
      )}

      {/* ── Artifact References View ──────────────────── */}
      {view === 'refs' && (
        <div className="space-y-4">
          {artifactRefs.length === 0 ? (
            <EmptyState icon={Link2} title="No artifact references" description="Artifact references from PM Again and QA Again will appear here." />
          ) : (
            <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="text-left px-4 py-3 font-medium text-gray-500">System</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-500">Type</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-500">ID</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-500">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {artifactRefs.map((ref) => (
                    <tr key={ref.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 text-xs rounded-full bg-indigo-50 text-indigo-700">{ref.owner_system}</span>
                      </td>
                      <td className="px-4 py-3 text-gray-600">{ref.artifact_type}</td>
                      <td className="px-4 py-3 font-mono text-xs text-gray-600">{ref.external_id}</td>
                      <td className="px-4 py-3 text-gray-500">{ref.status || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {traceLinks.length > 0 && (
            <div className="mt-6">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Trace Links</h3>
              <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium text-gray-500">Source</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-500">Link</th>
                      <th className="text-left px-4 py-3 font-medium text-gray-500">Target</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {traceLinks.map((link) => (
                      <tr key={link.id} className="hover:bg-gray-50">
                        <td className="px-4 py-3">
                          <span className="text-xs font-medium text-gray-700">{link.source_type}</span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2 text-xs text-gray-400">
                            <div className="w-12 h-px bg-gray-300" />
                            <span className="text-gray-600">{link.link_type}</span>
                            <ArrowRight size={12} />
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          {link.target_ref ? (
                            <div className="flex items-center gap-2">
                              <span className="px-1.5 py-0.5 text-xs rounded bg-indigo-50 text-indigo-700">{link.target_ref.owner_system}</span>
                              <span className="font-mono text-xs text-gray-600">{link.target_ref.external_id}</span>
                            </div>
                          ) : (
                            <span className="text-xs text-gray-300">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Confirm Send Dialog ────────────────────────── */}
      {confirmSend && (
        <ConfirmDialog
          title={`Send Delivery Plan to ${confirmSend.name}`}
          message="This will send all approved requirements to PM Again for delivery planning. Continue?"
          confirmLabel="Send Plan"
          loading={sendingPlan}
          onConfirm={handleSendDeliveryPlan}
          onCancel={() => setConfirmSend(null)}
        />
      )}
    </div>
  );
}
