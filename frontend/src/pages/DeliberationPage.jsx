import { useEffect, useState } from 'react';
import {
  Gavel, Plus, Users, Zap, Shield, AlertTriangle, CheckCircle2, XCircle,
  Eye, MessageSquare, Edit3, Flag, Clock, ArrowRight, RefreshCw,
} from 'lucide-react';
import { toast } from 'sonner';
import { CardSkeleton } from '../components/PageSkeleton';
import EmptyState from '../components/EmptyState';
import StatusBadge from '../components/StatusBadge';

const API = '/api/deliberation';

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

const TRIGGERS = [
  'HIGH_IMPACT', 'LOW_CONFIDENCE', 'CONFLICTING_REQUIREMENTS', 'CROSS_DOMAIN',
  'SECURITY_CONCERN', 'RELEASE_GATE', 'ARCHITECTURE_DECISION', 'CRITICAL_DEFECT',
  'HUMAN_REQUESTED_REVIEW', 'RANDOM_AUDIT_SAMPLE',
];

export default function DeliberationPage() {
  const [loading, setLoading] = useState(true);
  const [cases, setCases] = useState([]);
  const [selectedCase, setSelectedCase] = useState(null);
  const [caseDetail, setCaseDetail] = useState(null);
  const [skills, setSkills] = useState([]);

  // New case form
  const [showNew, setShowNew] = useState(false);
  const [newCase, setNewCase] = useState({ title: '', trigger: 'HUMAN_REQUESTED_REVIEW', task: '', criteria: '', skill_id: '' });

  // Submission form
  const [showSubmit, setShowSubmit] = useState(false);
  const [submitForm, setSubmitForm] = useState({ member_id: '', conclusion: '', recommended_action: '', confidence: 0.7, evidence_quality: 0.7 });

  // Critique form
  const [showCritique, setShowCritique] = useState(false);
  const [critiqueForm, setCritiqueForm] = useState({ reviewer_member_id: '', target_submission_id: '', target_label: '', strengths: '', weaknesses: '', overall_assessment: '' });

  const loadAll = async () => {
    try {
      const [c, s] = await Promise.all([
        fetchJSON(API),
        fetchJSON('/api/skills'),
      ]);
      setCases(c);
      setSkills(s);
    } catch { toast.error('Failed to load'); } finally { setLoading(false); }
  };

  useEffect(() => { loadAll(); }, []);

  const loadDetail = async (caseId) => {
    try {
      const d = await fetchJSON(`${API}/${caseId}`);
      setCaseDetail(d);
    } catch { toast.error('Failed to load case detail'); }
  };

  const handleStart = async (e) => {
    e.preventDefault();
    try {
      const result = await fetchJSON(`${API}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...newCase, project_slug: '' }),
      });
      toast.success(`Panel built: ${result.panel_size} members across ${new Set(result.members.map(m => m.provider)).size} providers`);
      setShowNew(false);
      setNewCase({ title: '', trigger: 'HUMAN_REQUESTED_REVIEW', task: '', criteria: '', skill_id: '' });
      loadAll();
    } catch (err) { toast.error(err.message); }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await fetchJSON(`${API}/${selectedCase}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(submitForm),
      });
      toast.success('Submission recorded');
      setShowSubmit(false);
      loadDetail(selectedCase);
    } catch (err) { toast.error(err.message); }
  };

  const handleCritique = async (e) => {
    e.preventDefault();
    try {
      await fetchJSON(`${API}/${selectedCase}/critique`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...critiqueForm,
          strengths: critiqueForm.strengths.split('\n').filter(Boolean),
          weaknesses: critiqueForm.weaknesses.split('\n').filter(Boolean),
        }),
      });
      toast.success('Critique recorded');
      setShowCritique(false);
      loadDetail(selectedCase);
    } catch (err) { toast.error(err.message); }
  };

  const handleDecide = async (outcome) => {
    try {
      await fetchJSON(`${API}/${selectedCase}/decide`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          outcome,
          final_decision: `Decision rendered: ${outcome}`,
          human_approved: true,
          human_approved_by: 'user',
        }),
      });
      toast.success('Decision recorded');
      loadAll();
      loadDetail(selectedCase);
    } catch (err) { toast.error(err.message); }
  };

  if (loading) return <CardSkeleton count={4} />;

  const statusColor = (s) => {
    if (s === 'decided') return 'text-emerald-600';
    if (s?.includes('complete') || s === 'judging') return 'text-blue-600';
    if (s?.includes('alert')) return 'text-red-600';
    return 'text-amber-600';
  };

  return (
    <div className="page-shell py-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <Gavel size={22} className="text-amber-600" />
            Deliberation
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Multi-agent deliberation with anti-convergence governance — independent first-pass, blind review, dissent preservation.
          </p>
        </div>
        <button onClick={() => setShowNew(true)}
          className="inline-flex items-center gap-1.5 px-3 py-2 bg-amber-600 text-white text-sm font-medium rounded-lg hover:bg-amber-700 transition">
          <Plus size={16} /> New Deliberation
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Case List */}
        <div className="lg:col-span-1 space-y-3">
          {cases.length === 0 ? (
            <EmptyState icon={Gavel} title="No deliberations" description="Start a multi-agent review for high-impact decisions." />
          ) : (
            cases.map((c) => (
              <button key={c.id}
                onClick={() => { setSelectedCase(c.id); loadDetail(c.id); }}
                className={`w-full text-left bg-white border rounded-xl p-4 transition-all card-premium ${
                  selectedCase === c.id ? 'border-amber-400 ring-2 ring-amber-100' : 'border-gray-200 hover:border-amber-200'
                }`}>
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-gray-900 text-sm truncate">{c.title}</span>
                  <StatusBadge status={c.status} />
                </div>
                <div className="flex gap-3 text-xs text-gray-400">
                  <span className="flex items-center gap-1"><Users size={11} />{c.member_count}</span>
                  <span className="flex items-center gap-1"><MessageSquare size={11} />{c.submission_count}</span>
                  {c.dissent_count > 0 && <span className="flex items-center gap-1 text-amber-600"><AlertTriangle size={11} />{c.dissent_count}</span>}
                </div>
              </button>
            ))
          )}
        </div>

        {/* Case Detail */}
        <div className="lg:col-span-2">
          {!caseDetail ? (
            <div className="bg-white border border-gray-200 rounded-xl p-8 text-center">
              <Gavel size={40} className="text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500 text-sm">Select a deliberation case to view details</p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Header */}
              <div className="bg-white border border-gray-200 rounded-xl p-5 card-premium">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-semibold text-gray-900">{caseDetail.title}</h3>
                  <StatusBadge status={caseDetail.status} />
                </div>
                <div className="text-sm text-gray-700">{caseDetail.source_packet?.task || caseDetail.decision_criteria}</div>
                <div className="mt-3 flex gap-4 text-xs text-gray-400">
                  <span>Trigger: {caseDetail.trigger}</span>
                  <span>Outcome: {caseDetail.outcome || 'pending'}</span>
                </div>
              </div>

              {/* Panel Members */}
              <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                <div className="px-5 py-3 bg-gray-50 border-b border-gray-100 text-xs font-medium text-gray-500 uppercase flex items-center gap-2">
                  <Users size={14} /> Panel ({caseDetail.members?.length || 0} members)
                </div>
                <div className="divide-y divide-gray-100">
                  {(caseDetail.members || []).map((m) => (
                    <div key={m.id} className="px-5 py-3 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="w-7 h-7 rounded-full bg-amber-100 text-amber-700 text-xs font-bold flex items-center justify-center">
                          {m.label?.replace('Candidate ', '')}
                        </span>
                        <div>
                          <div className="text-sm font-medium text-gray-900">{m.role?.replace(/_/g, ' ')}</div>
                          <div className="text-xs text-gray-400">{m.provider} · {m.model}</div>
                        </div>
                      </div>
                      {m.has_submitted ? <CheckCircle2 size={16} className="text-emerald-500" /> : <Clock size={16} className="text-gray-300" />}
                    </div>
                  ))}
                </div>
              </div>

              {/* Submissions */}
              {(caseDetail.submissions || []).length > 0 && (
                <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                  <div className="px-5 py-3 bg-gray-50 border-b border-gray-100 text-xs font-medium text-gray-500 uppercase flex items-center gap-2">
                    <MessageSquare size={14} /> Independent Submissions
                  </div>
                  <div className="divide-y divide-gray-100">
                    {caseDetail.submissions.map((s, i) => (
                      <div key={s.id} className="px-5 py-3">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-bold text-amber-600">Candidate {String.fromCharCode(65 + i)}</span>
                          <span className="text-xs text-gray-400">Confidence: {s.confidence} | Evidence: {s.evidence_quality}</span>
                        </div>
                        <p className="text-sm text-gray-700">{s.conclusion}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Dissents */}
              {(caseDetail.dissents || []).length > 0 && (
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-5">
                  <div className="flex items-center gap-2 text-amber-700 font-medium text-sm mb-3">
                    <AlertTriangle size={16} /> Dissent Records ({caseDetail.dissents.length})
                  </div>
                  {caseDetail.dissents.map((d) => (
                    <div key={d.id} className="text-sm text-amber-800 mb-2">
                      <span className="font-medium">Minority position:</span> {d.position}
                      <StatusBadge status={d.status} className="ml-2" />
                    </div>
                  ))}
                </div>
              )}

              {/* Conformity Alerts */}
              {(caseDetail.diversity_snapshots || []).some(s => (s.conformity_alerts || []).length > 0) && (
                <div className="bg-red-50 border border-red-200 rounded-xl p-5">
                  <div className="flex items-center gap-2 text-red-700 font-medium text-sm mb-2">
                    <Flag size={16} /> Conformity Alerts
                  </div>
                  {caseDetail.diversity_snapshots.filter(s => (s.conformity_alerts || []).length > 0).map((s) =>
                    s.conformity_alerts.map((a, i) => (
                      <div key={i} className="text-xs text-red-700">{a}</div>
                    ))
                  )}
                </div>
              )}

              {/* Actions */}
              {caseDetail.status !== 'decided' && (
                <div className="flex flex-wrap gap-2">
                  <button onClick={() => { setShowSubmit(true); setSubmitForm({ ...submitForm, member_id: caseDetail.members?.[0]?.id || '' }); }}
                    className="px-3 py-1.5 text-xs font-medium text-amber-700 bg-amber-50 rounded-lg hover:bg-amber-100 transition flex items-center gap-1">
                    <Edit3 size={12} /> Submit (as panel member)
                  </button>
                  <button onClick={() => { setShowCritique(true); setCritiqueForm({ ...critiqueForm, reviewer_member_id: caseDetail.members?.[0]?.id || '' }); }}
                    className="px-3 py-1.5 text-xs font-medium text-blue-700 bg-blue-50 rounded-lg hover:bg-blue-100 transition flex items-center gap-1">
                    <Eye size={12} /> Blind Critique
                  </button>
                  <button onClick={() => handleDecide('SUPPORTED_AGREEMENT')}
                    className="px-3 py-1.5 text-xs font-medium text-emerald-700 bg-emerald-50 rounded-lg hover:bg-emerald-100 transition flex items-center gap-1">
                    <CheckCircle2 size={12} /> Decide (Agreement)
                  </button>
                  <button onClick={() => handleDecide('SUPPORTED_MAJORITY_WITH_DISSENT')}
                    className="px-3 py-1.5 text-xs font-medium text-amber-700 bg-amber-50 rounded-lg hover:bg-amber-100 transition flex items-center gap-1">
                    <AlertTriangle size={12} /> Decide (With Dissent)
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ════════ MODALS ════════ */}
      {showNew && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setShowNew(false)} />
          <div className="relative bg-white rounded-xl shadow-2xl max-w-lg w-full mx-4 p-6 z-10 max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">New Deliberation</h2>
            <form onSubmit={handleStart} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
                <input required value={newCase.title} onChange={e => setNewCase({ ...newCase, title: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-amber-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Trigger</label>
                <select value={newCase.trigger} onChange={e => setNewCase({ ...newCase, trigger: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white focus:ring-2 focus:ring-amber-500">
                  {TRIGGERS.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Task Description</label>
                <textarea rows={3} value={newCase.task} onChange={e => setNewCase({ ...newCase, task: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-amber-500 resize-none"
                  placeholder="Describe the question or decision to deliberate..." />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Decision Criteria</label>
                <textarea rows={2} value={newCase.criteria} onChange={e => setNewCase({ ...newCase, criteria: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-amber-500 resize-none" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Skill (optional)</label>
                <select value={newCase.skill_id} onChange={e => setNewCase({ ...newCase, skill_id: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white focus:ring-2 focus:ring-amber-500">
                  <option value="">No specific skill</option>
                  {skills.map(s => <option key={s.id} value={s.skill_id}>{s.name}</option>)}
                </select>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setShowNew(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50">Cancel</button>
                <button type="submit"
                  className="px-4 py-2 text-sm font-medium text-white bg-amber-600 rounded-lg hover:bg-amber-700 flex items-center gap-1.5">
                  <Zap size={14} /> Build Panel & Start
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Submit Modal */}
      {showSubmit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setShowSubmit(false)} />
          <div className="relative bg-white rounded-xl shadow-2xl max-w-lg w-full mx-4 p-6 z-10">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Independent Submission</h2>
            <p className="text-xs text-amber-600 bg-amber-50 rounded-lg px-3 py-2 mb-4">
              ⚠️ This is an independent first-pass. You cannot see peer answers.
            </p>
            <form onSubmit={handleSubmit} className="space-y-4">
              <select value={submitForm.member_id} onChange={e => setSubmitForm({ ...submitForm, member_id: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white">
                <option value="">Select panel member...</option>
                {(caseDetail?.members || []).map(m => (
                  <option key={m.id} value={m.id}>{m.label} — {m.role}</option>
                ))}
              </select>
              <textarea rows={3} value={submitForm.conclusion} onChange={e => setSubmitForm({ ...submitForm, conclusion: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg resize-none" placeholder="Conclusion..." required />
              <textarea rows={2} value={submitForm.recommended_action} onChange={e => setSubmitForm({ ...submitForm, recommended_action: e.target.value })}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg resize-none" placeholder="Recommended action..." />
              <div className="flex gap-3">
                <div className="flex-1">
                  <label className="text-xs text-gray-500">Confidence ({submitForm.confidence})</label>
                  <input type="range" min="0" max="1" step="0.1" value={submitForm.confidence}
                    onChange={e => setSubmitForm({ ...submitForm, confidence: parseFloat(e.target.value) })}
                    className="w-full" />
                </div>
                <div className="flex-1">
                  <label className="text-xs text-gray-500">Evidence Quality ({submitForm.evidence_quality})</label>
                  <input type="range" min="0" max="1" step="0.1" value={submitForm.evidence_quality}
                    onChange={e => setSubmitForm({ ...submitForm, evidence_quality: parseFloat(e.target.value) })}
                    className="w-full" />
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setShowSubmit(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg">Cancel</button>
                <button type="submit"
                  className="px-4 py-2 text-sm font-medium text-white bg-amber-600 rounded-lg hover:bg-amber-700">Submit</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
