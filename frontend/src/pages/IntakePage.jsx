import { useEffect, useState, useRef } from 'react';
import {
  FileText, Upload, Zap, BarChart3, AlertTriangle, CheckCircle2,
  Clock, Target, Layers, ArrowRight, Download, Trash2, Activity,
  GanttChartSquare, TrendingUp, Shield, Filter,
} from 'lucide-react';
import { toast } from 'sonner';
import { CardSkeleton } from '../components/PageSkeleton';
import EmptyState from '../components/EmptyState';
import StatusBadge from '../components/StatusBadge';

export default function IntakePage({ slug }) {
  const [loading, setLoading] = useState(true);
  const [sessions, setSessions] = useState([]);
  const [selectedSession, setSelectedSession] = useState(null);
  const [sessionData, setSessionData] = useState(null);
  const [inputText, setInputText] = useState('');
  const [parsing, setParsing] = useState(false);
  const [activeView, setActiveView] = useState('decompose'); // decompose, similarity, risk
  const textareaRef = useRef(null);

  const loadSessions = async () => {
    try {
      const res = await fetch(`/api/${slug}/intake/sessions`, { credentials: 'include' });
      const data = await res.json();
      setSessions(data);
    } catch { /* ignore */ } finally { setLoading(false); }
  };

  useEffect(() => { loadSessions(); }, [slug]);

  const loadSession = async (id) => {
    try {
      const res = await fetch(`/api/${slug}/intake/sessions/${id}`, { credentials: 'include' });
      const data = await res.json();
      setSessionData(data);
      setSelectedSession(id);
    } catch { toast.error('Failed to load session'); }
  };

  const handleParse = async () => {
    if (!inputText.trim()) return;
    setParsing(true);
    try {
      const res = await fetch(`/api/${slug}/intake/parse`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ content: inputText, source_type: 'text', source_name: 'Manual Input' }),
      });
      const data = await res.json();
      toast.success(`${data.function_count} functions decomposed`);
      setInputText('');
      loadSessions();
      // Auto-select new session
      setTimeout(() => loadSession(data.session_id), 300);
    } catch (e) {
      toast.error('Parse failed');
    } finally {
      setParsing(false);
    }
  };

  const cxColor = (level) => {
    switch (level) {
      case 'trivial': return 'text-gray-400 bg-gray-50';
      case 'simple': return 'text-emerald-600 bg-emerald-50';
      case 'moderate': return 'text-blue-600 bg-blue-50';
      case 'complex': return 'text-amber-600 bg-amber-50';
      case 'very_complex': return 'text-red-600 bg-red-50';
      default: return 'text-gray-400 bg-gray-50';
    }
  };

  const riskColor = (level) => {
    switch (level) {
      case 'low': return 'text-emerald-600';
      case 'medium': return 'text-amber-600';
      case 'high': return 'text-orange-600';
      case 'critical': return 'text-red-600';
      default: return 'text-gray-400';
    }
  };

  const moduleColor = (mod) => {
    switch (mod) {
      case 'CONDUCTOR': return 'bg-purple-100 text-purple-700';
      case 'PM_AGAIN': return 'bg-indigo-100 text-indigo-700';
      case 'QA_AGAIN': return 'bg-emerald-100 text-emerald-700';
      case 'DEV': return 'bg-blue-100 text-blue-700';
      default: return 'bg-gray-100 text-gray-600';
    }
  };

  if (loading) return <CardSkeleton count={4} />;

  const funcs = sessionData?.functions || [];
  const risk = sessionData?.risk;
  const sims = (sessionData?.similarities || []).filter(s => s.level !== 'none');
  const totalEffort = funcs.reduce((sum, f) => sum + (f.effort_person_days || 0), 0);

  return (
    <div className="page-shell py-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <FileText size={22} className="text-amber-600" />
            Intake & Decomposition
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Parse text, Excel, Markdown → decompose into function list → analyze complexity, similarity, effort, risk → distribute.
          </p>
        </div>
      </div>

      {/* Input Area */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 card-premium">
        <textarea
          ref={textareaRef}
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          rows={5}
          className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-amber-500 resize-none font-mono"
          placeholder={`Paste requirements, user stories, or feature descriptions here...

Example:
1. User login with email/password and OAuth2 support
2. Create and edit Production BOM with version history
3. Circular reference detection — prevent self-reference on save
4. BOM comparison tool — diff two versions side by side
5. Export BOM to Excel with cost roll-up
6. Approval workflow with multi-level sign-off
7. Real-time inventory integration with ERP system
8. Audit trail for all BOM changes with user attribution
9. Role-based access: viewers, editors, approvers
10. Performance: sub-second search across 50K+ BOM items`}
        />
        <div className="flex justify-between items-center mt-3">
          <span className="text-xs text-gray-400">
            Paste any text — lists, paragraphs, markdown, or structured requirements.
          </span>
          <button
            onClick={handleParse}
            disabled={parsing || !inputText.trim()}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-amber-600 text-white text-sm font-medium rounded-lg hover:bg-amber-700 disabled:opacity-50 transition"
          >
            {parsing ? (
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <Zap size={16} />
            )}
            {parsing ? 'Analyzing...' : 'Decompose & Analyze'}
          </button>
        </div>
      </div>

      {/* Session List + Detail */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Sessions sidebar */}
        <div className="lg:col-span-1 space-y-2 max-h-[600px] overflow-y-auto">
          {sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => loadSession(s.id)}
              className={`w-full text-left bg-white border rounded-xl p-3 transition-all ${
                selectedSession === s.id ? 'border-amber-400 ring-2 ring-amber-100' : 'border-gray-200 hover:border-amber-200'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-900 truncate">
                  {s.source_name || s.source_type}
                </span>
                <StatusBadge status={s.status} />
              </div>
              <div className="text-xs text-gray-400 mt-1">
                {s.function_count} functions · {new Date(s.created_at).toLocaleDateString()}
              </div>
            </button>
          ))}
          {sessions.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-8">No intake sessions yet. Paste text above to start.</p>
          )}
        </div>

        {/* Detail */}
        <div className="lg:col-span-2">
          {!sessionData ? (
            <div className="bg-white border border-gray-200 rounded-xl p-8 text-center">
              <Upload size={40} className="text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500 text-sm">Select a session or paste text above to decompose</p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Summary Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { label: 'Functions', value: funcs.length, icon: Layers, color: 'text-amber-600', bg: 'bg-amber-50' },
                  { label: 'Total Effort', value: `${totalEffort.toFixed(1)}d`, icon: Clock, color: 'text-blue-600', bg: 'bg-blue-50' },
                  { label: 'Similar Pairs', value: sims.length, icon: Activity, color: 'text-purple-600', bg: 'bg-purple-50' },
                  { label: 'Risk Level', value: risk?.level || 'N/A', icon: Shield, color: riskColor(risk?.level), bg: 'bg-red-50' },
                ].map(({ label, value, icon: Icon, color, bg }) => (
                  <div key={label} className="bg-white border border-gray-200 rounded-xl p-3 card-premium">
                    <div className={`w-7 h-7 rounded-lg ${bg} flex items-center justify-center mb-1.5`}>
                      <Icon size={14} className={color} />
                    </div>
                    <div className="text-lg font-bold text-gray-900">{value}</div>
                    <div className="text-xs text-gray-500">{label}</div>
                  </div>
                ))}
              </div>

              {/* View tabs */}
              <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit">
                {[
                  { key: 'decompose', label: 'Functions', icon: Layers },
                  { key: 'similarity', label: `Similarity (${sims.length})`, icon: Activity },
                  { key: 'risk', label: 'Risk Forecast', icon: Shield },
                ].map(({ key, label, icon: Icon }) => (
                  <button key={key} onClick={() => setActiveView(key)}
                    className={`flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-md transition ${
                      activeView === key ? 'bg-white text-amber-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                    }`}>
                    <Icon size={13} />{label}
                  </button>
                ))}
              </div>

              {/* Function List */}
              {activeView === 'decompose' && (
                <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                  <div className="divide-y divide-gray-100 max-h-[500px] overflow-y-auto">
                    {funcs.map((f) => (
                      <div key={f.id} className="px-4 py-3 hover:bg-gray-50 transition-colors">
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-2 min-w-0">
                            <code className="text-[10px] font-mono text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded">{f.code}</code>
                            <span className="text-sm font-medium text-gray-900 truncate">{f.title}</span>
                          </div>
                          <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium ${moduleColor(f.target_module)}`}>
                            {f.target_module}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 text-xs text-gray-400">
                          <span className={`inline-flex px-1.5 py-0.5 rounded ${cxColor(f.complexity_level)}`}>
                            {f.complexity_level} ({(f.complexity_score || 0).toFixed(0)})
                          </span>
                          <span>{f.effort_person_days?.toFixed(1)}d</span>
                          <span>{(f.effort_fp || 0).toFixed(0)} FP</span>
                          {f.category && <span className="text-gray-300">· {f.category}</span>}
                        </div>
                        {f.description && (
                          <p className="text-xs text-gray-500 mt-1 line-clamp-1">{f.description}</p>
                        )}
                      </div>
                    ))}
                  </div>
                  {/* Complexity Distribution */}
                  {funcs.length > 0 && (
                    <div className="px-4 py-2 bg-gray-50 border-t border-gray-100 flex gap-1.5">
                      {['trivial', 'simple', 'moderate', 'complex', 'very_complex'].map((lvl) => {
                        const count = funcs.filter(f => f.complexity_level === lvl).length;
                        if (count === 0) return null;
                        return (
                          <span key={lvl} className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${cxColor(lvl)}`}>
                            {lvl}: {count}
                          </span>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* Similarity View */}
              {activeView === 'similarity' && (
                <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                  {sims.length === 0 ? (
                    <div className="p-6"><EmptyState icon={Activity} title="No significant similarities" description="Functions are sufficiently distinct." /></div>
                  ) : (
                    <div className="divide-y divide-gray-100">
                      {sims.map((s, i) => {
                        const fa = funcs.find(f => f.id === s.function_a_id);
                        const fb = funcs.find(f => f.id === s.function_b_id);
                        return (
                          <div key={i} className="px-4 py-3 hover:bg-gray-50">
                            <div className="flex items-center justify-between mb-1">
                              <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${
                                s.level === 'duplicate' ? 'bg-red-100 text-red-700' :
                                s.level === 'high' ? 'bg-amber-100 text-amber-700' :
                                'bg-blue-100 text-blue-700'
                              }`}>
                                {s.level.toUpperCase()} ({(s.score * 100).toFixed(0)}%)
                              </span>
                            </div>
                            <div className="text-xs text-gray-600">
                              <span className="font-mono text-amber-600">{fa?.code}</span> {fa?.title?.slice(0, 50)}
                              <span className="mx-2 text-gray-300">↔</span>
                              <span className="font-mono text-amber-600">{fb?.code}</span> {fb?.title?.slice(0, 50)}
                            </div>
                            {s.recommendation && (
                              <p className="text-xs text-amber-700 mt-1">{s.recommendation}</p>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* Risk View */}
              {activeView === 'risk' && risk && (
                <div className="space-y-3">
                  <div className="bg-white border border-gray-200 rounded-xl p-5 card-premium">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="font-semibold text-gray-900">Risk Assessment</h4>
                      <span className={`text-sm font-bold ${riskColor(risk.level)}`}>
                        {risk.level.toUpperCase()} — Score: {risk.overall_score?.toFixed(2)}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600">{risk.summary}</p>
                    <div className="mt-2 text-sm text-gray-500">
                      Recommended schedule buffer: <span className="font-bold text-amber-600">{risk.schedule_buffer_days} days</span>
                    </div>
                  </div>
                  {(risk.items || []).map((item, i) => (
                    <div key={i} className="bg-white border border-gray-200 rounded-xl p-4 card-premium">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium text-gray-900">{item.category}</span>
                        <span className={`text-xs font-bold ${riskColor(item.level)}`}>
                          {item.level?.toUpperCase()} — {(item.severity * 100).toFixed(0)}%
                        </span>
                      </div>
                      <p className="text-xs text-gray-600">{item.description}</p>
                      <p className="text-xs text-amber-700 mt-1 bg-amber-50 rounded px-2 py-1">
                        💡 {item.mitigation}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
