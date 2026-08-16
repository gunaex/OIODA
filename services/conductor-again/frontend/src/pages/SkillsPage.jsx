import { useEffect, useState } from 'react';
import { Zap, Plus, CheckCircle2, Clock, Ban, Play, BookOpen, Shield } from 'lucide-react';
import { toast } from 'sonner';
import { CardSkeleton } from '../components/PageSkeleton';
import EmptyState from '../components/EmptyState';
import StatusBadge from '../components/StatusBadge';

const API = '/api/skills';

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

const CATEGORIES = [
  { key: 'vision', label: 'Vision', icon: BookOpen },
  { key: 'requirement', label: 'Requirement', icon: Shield },
  { key: 'analysis', label: 'Analysis', icon: Zap },
  { key: 'planning', label: 'Planning', icon: CheckCircle2 },
  { key: 'review', label: 'Review', icon: BookOpen },
  { key: 'decision', label: 'Decision', icon: Play },
];

export default function SkillsPage() {
  const [loading, setLoading] = useState(true);
  const [skills, setSkills] = useState([]);
  const [versions, setVersions] = useState({});
  const [executions, setExecutions] = useState([]);
  const [activeTab, setActiveTab] = useState('catalog');
  const [showAdd, setShowAdd] = useState(false);
  const [selectedSkill, setSelectedSkill] = useState(null);

  // Add skill form
  const [newSkill, setNewSkill] = useState({
    skill_id: '', name: '', description: '', category: 'vision',
  });

  // Version form
  const [newVersion, setNewVersion] = useState({
    system_instructions: '', prompt_template: '', release_notes: '',
  });
  const [showAddVersion, setShowAddVersion] = useState(false);

  const loadAll = async () => {
    try {
      const s = await fetchJSON(API);
      setSkills(s);
      const e = await fetchJSON(`${API}/executions?limit=10`);
      setExecutions(e);
    } catch (e) {
      toast.error('Failed to load skills');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAll(); }, []);

  const loadVersions = async (skillDbId) => {
    if (versions[skillDbId]) return;
    try {
      const v = await fetchJSON(`${API}/${skillDbId}/versions`);
      setVersions((prev) => ({ ...prev, [skillDbId]: v }));
    } catch { /* ignore */ }
  };

  const handleCreateSkill = async (e) => {
    e.preventDefault();
    try {
      const s = await fetchJSON(API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newSkill),
      });
      toast.success('Skill created');
      setSkills((prev) => [s, ...prev]);
      setShowAdd(false);
      setNewSkill({ skill_id: '', name: '', description: '', category: 'vision' });
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handlePublishVersion = async (versionId) => {
    try {
      await fetchJSON(`${API}/versions/${versionId}/publish`, { method: 'POST' });
      toast.success('Version published');
      loadAll();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handleAddVersion = async (e) => {
    e.preventDefault();
    if (!selectedSkill) return;
    try {
      const v = await fetchJSON(`${API}/${selectedSkill.id}/versions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skill_db_id: selectedSkill.id, ...newVersion }),
      });
      toast.success(`Version ${v.version} created`);
      setVersions((prev) => ({
        ...prev,
        [selectedSkill.id]: [v, ...(prev[selectedSkill.id] || [])],
      }));
      setShowAddVersion(false);
      setNewVersion({ system_instructions: '', prompt_template: '', release_notes: '' });
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handleExecute = async (skillId) => {
    try {
      const result = await fetchJSON(`${API}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          skill_id: skillId,
          project_slug: '',
          input_data: { test: true },
          selection_mode: 'AUTO',
        }),
      });
      toast.success(
        `Router: ${result.candidates_considered} resources → ${result.candidates_eligible} eligible → ${result.primary_display_name || 'none'}`
      );
      loadAll();
    } catch (err) {
      toast.error(err.message);
    }
  };

  if (loading) return <CardSkeleton count={6} />;

  const versionStatusIcon = (status) => {
    switch (status) {
      case 'published': return <CheckCircle2 size={14} className="text-emerald-500" />;
      case 'draft': return <Clock size={14} className="text-amber-500" />;
      case 'revoked': return <Ban size={14} className="text-red-500" />;
      default: return <Clock size={14} className="text-gray-400" />;
    }
  };

  return (
    <div className="page-shell py-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <Zap size={22} className="text-amber-600" />
            Skill Registry
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Governed, versioned Skill packages — the capability catalog powering every AI-driven workflow.
          </p>
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="inline-flex items-center gap-1.5 px-3 py-2 bg-amber-600 text-white text-sm font-medium rounded-lg hover:bg-amber-700 transition focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2"
        >
          <Plus size={16} />
          New Skill
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit">
        {[
          { key: 'catalog', label: 'Catalog' },
          { key: 'executions', label: 'Executions' },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`px-3 py-1.5 text-sm font-medium rounded-md transition ${
              activeTab === key
                ? 'bg-white text-amber-700 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ════════ CATALOG ════════ */}
      {activeTab === 'catalog' && (
        <div className="space-y-4">
          {skills.length === 0 ? (
            <EmptyState icon={Zap} title="No skills yet" description="Create your first governed Skill to start orchestrating AI capabilities." />
          ) : (
            skills.map((s) => (
              <div key={s.id} className="bg-white border border-gray-200 rounded-xl overflow-hidden card-premium">
                {/* Skill header */}
                <div className="px-5 py-4 flex items-center justify-between hover:bg-gray-50/50 cursor-pointer"
                  onClick={() => { setSelectedSkill(selectedSkill?.id === s.id ? null : s); loadVersions(s.id); }}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-9 h-9 rounded-lg bg-amber-50 flex items-center justify-center">
                      <Zap size={18} className="text-amber-600" />
                    </div>
                    <div className="min-w-0">
                      <div className="font-semibold text-gray-900 text-sm">{s.name}</div>
                      <code className="text-xs text-gray-400">{s.skill_id} · v{s.current_version}</code>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {s.category && (
                      <span className="text-xs text-gray-400 bg-gray-50 px-1.5 py-0.5 rounded">{s.category}</span>
                    )}
                    <StatusBadge status={s.status} />
                    <button
                      onClick={(e) => { e.stopPropagation(); handleExecute(s.skill_id); }}
                      className="p-1.5 text-amber-600 hover:bg-amber-50 rounded-lg transition-colors"
                      title="Test AUTO router"
                    >
                      <Play size={14} />
                    </button>
                  </div>
                </div>

                {/* Expanded: versions */}
                {selectedSkill?.id === s.id && (
                  <div className="border-t border-gray-100 bg-gray-50/50 px-5 py-3">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Versions</span>
                      <button
                        onClick={() => setShowAddVersion(true)}
                        className="text-xs font-medium text-amber-600 hover:text-amber-700 flex items-center gap-1"
                      >
                        <Plus size={12} /> New Version
                      </button>
                    </div>
                    {s.description && (
                      <p className="text-xs text-gray-500 mb-3">{s.description}</p>
                    )}
                    {(versions[s.id] || []).length === 0 ? (
                      <p className="text-xs text-gray-400 italic">No versions yet. Create one to start.</p>
                    ) : (
                      <div className="space-y-2">
                        {(versions[s.id] || []).map((v) => (
                          <div key={v.id} className="flex items-center justify-between bg-white rounded-lg px-3 py-2 border border-gray-100">
                            <div className="flex items-center gap-2">
                              {versionStatusIcon(v.status)}
                              <span className="text-sm font-medium text-gray-700">v{v.version}</span>
                              {v.checksum && (
                                <code className="text-[10px] text-gray-400">{v.checksum.slice(0, 8)}</code>
                              )}
                              {v.release_notes && (
                                <span className="text-xs text-gray-400 truncate max-w-[200px]">— {v.release_notes}</span>
                              )}
                            </div>
                            <div className="flex items-center gap-1">
                              {v.status === 'draft' && (
                                <button
                                  onClick={() => handlePublishVersion(v.id)}
                                  className="px-2 py-0.5 text-[10px] font-medium text-emerald-700 bg-emerald-50 rounded hover:bg-emerald-100 transition"
                                >
                                  Publish
                                </button>
                              )}
                              {v.status === 'published' && v.published_by && (
                                <span className="text-[10px] text-gray-400">by {v.published_by}</span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* ════════ EXECUTIONS ════════ */}
      {activeTab === 'executions' && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          {executions.length === 0 ? (
            <div className="p-6">
              <EmptyState icon={Play} title="No executions yet" description="Execute a Skill through the AUTO router to see results here." />
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {executions.map((ex) => (
                <div key={ex.id} className="px-5 py-3 flex items-center justify-between hover:bg-gray-50">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-gray-900 truncate">{ex.request_id}</div>
                    <div className="text-xs text-gray-400">
                      {ex.project_slug || '(no project)'} · {ex.selection_mode} · {ex.latency_ms}ms
                      {ex.estimated_cost_usd > 0 && ` · $${ex.estimated_cost_usd.toFixed(4)}`}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-xs text-gray-400">{ex.input_tokens}+{ex.output_tokens} tok</span>
                    <StatusBadge status={ex.status} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ════════ ADD SKILL MODAL ════════ */}
      {showAdd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setShowAdd(false)} />
          <div className="relative bg-white rounded-xl shadow-2xl max-w-lg w-full mx-4 p-6 z-10">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Create Skill</h2>
            <form onSubmit={handleCreateSkill} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Skill ID</label>
                <input required value={newSkill.skill_id} onChange={(e) => setNewSkill({ ...newSkill, skill_id: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 font-mono"
                  placeholder="requirement-clarifier" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input required value={newSkill.name} onChange={(e) => setNewSkill({ ...newSkill, name: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
                  placeholder="Requirement Clarifier" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
                <select value={newSkill.category} onChange={(e) => setNewSkill({ ...newSkill, category: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 bg-white">
                  {CATEGORIES.map((c) => (
                    <option key={c.key} value={c.key}>{c.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea rows={2} value={newSkill.description} onChange={(e) => setNewSkill({ ...newSkill, description: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 resize-none" />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setShowAdd(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition">Cancel</button>
                <button type="submit"
                  className="px-4 py-2 text-sm font-medium text-white bg-amber-600 rounded-lg hover:bg-amber-700 transition flex items-center gap-1.5">
                  <Plus size={14} /> Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ════════ ADD VERSION MODAL ════════ */}
      {showAddVersion && selectedSkill && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setShowAddVersion(false)} />
          <div className="relative bg-white rounded-xl shadow-2xl max-w-lg w-full mx-4 p-6 z-10">
            <h2 className="text-lg font-semibold text-gray-900 mb-1">New Version — {selectedSkill.name}</h2>
            <p className="text-sm text-gray-500 mb-4">Each version is immutable once published.</p>
            <form onSubmit={handleAddVersion} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">System Instructions</label>
                <textarea rows={3} value={newVersion.system_instructions} onChange={(e) => setNewVersion({ ...newVersion, system_instructions: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 resize-none font-mono"
                  placeholder="You are a requirement analysis specialist..." />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Prompt Template</label>
                <textarea rows={3} value={newVersion.prompt_template} onChange={(e) => setNewVersion({ ...newVersion, prompt_template: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 resize-none font-mono"
                  placeholder="Analyze the following requirement: {{input}}..." />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Release Notes</label>
                <input value={newVersion.release_notes} onChange={(e) => setNewVersion({ ...newVersion, release_notes: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
                  placeholder="Initial release" />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setShowAddVersion(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition">Cancel</button>
                <button type="submit"
                  className="px-4 py-2 text-sm font-medium text-white bg-amber-600 rounded-lg hover:bg-amber-700 transition flex items-center gap-1.5">
                  <Plus size={14} /> Create Version
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
