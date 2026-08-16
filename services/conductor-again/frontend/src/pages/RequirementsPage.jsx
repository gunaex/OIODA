import { useEffect, useState } from 'react';
import { Shield, Plus, Search, CheckCircle2, Clock, XCircle, Edit3, Filter, ArrowUpDown } from 'lucide-react';
import { toast } from 'sonner';
import { listRequirements, createRequirement } from '../api/client';
import { CardSkeleton } from '../components/PageSkeleton';
import EmptyState from '../components/EmptyState';
import StatusBadge from '../components/StatusBadge';
import ConfirmDialog from '../components/ConfirmDialog';
import MultiAIAnalysis from '../components/MultiAIAnalysis';

const STATUS_FILTERS = ['all', 'draft', 'clarifying', 'approved', 'change_proposed', 'superseded'];

export default function RequirementsPage({ slug }) {
  const [loading, setLoading] = useState(true);
  const [requirements, setRequirements] = useState([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [sortBy, setSortBy] = useState('code');

  // Create
  const [showCreate, setShowCreate] = useState(false);
  const [newReq, setNewReq] = useState({ code: '', title: '', description: '' });
  const [creating, setCreating] = useState(false);

  const load = async () => {
    try {
      const data = await listRequirements(slug);
      setRequirements(data);
    } catch { toast.error('Failed to load requirements'); } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [slug]);

  const handleCreate = async (e) => {
    e.preventDefault();
    setCreating(true);
    try {
      await createRequirement(slug, newReq);
      toast.success('Requirement created');
      setShowCreate(false);
      setNewReq({ code: '', title: '', description: '' });
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed');
    } finally { setCreating(false); }
  };

  // Filter + sort
  const filtered = requirements.filter(r => {
    if (statusFilter !== 'all' && r.status !== statusFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      return r.code.toLowerCase().includes(q) || r.title.toLowerCase().includes(q) || r.description.toLowerCase().includes(q);
    }
    return true;
  }).sort((a, b) => {
    if (sortBy === 'code') return a.code.localeCompare(b.code);
    if (sortBy === 'status') return a.status.localeCompare(b.status);
    if (sortBy === 'date') return new Date(b.updated_at) - new Date(a.updated_at);
    return 0;
  });

  if (loading) return <CardSkeleton count={6} />;

  const stats = {
    total: requirements.length,
    draft: requirements.filter(r => r.status === 'draft').length,
    approved: requirements.filter(r => r.baseline_approved).length,
    clarifying: requirements.filter(r => r.status === 'clarifying').length,
  };

  return (
    <div className="page-shell py-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <Shield size={22} className="text-amber-600" />
            Requirements
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Governed requirement baselines — every change is tracked and traceable.
          </p>
        </div>
        <button onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-1.5 px-3 py-2 bg-amber-600 text-white text-sm font-medium rounded-lg hover:bg-amber-700 transition">
          <Plus size={16} /> New Requirement
        </button>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Total', value: stats.total, color: 'text-gray-600', bg: 'bg-gray-50' },
          { label: 'Approved', value: stats.approved, color: 'text-emerald-600', bg: 'bg-emerald-50' },
          { label: 'Draft', value: stats.draft, color: 'text-amber-600', bg: 'bg-amber-50' },
          { label: 'Clarifying', value: stats.clarifying, color: 'text-blue-600', bg: 'bg-blue-50' },
        ].map(({ label, value, color, bg }) => (
          <div key={label} className={`${bg} rounded-xl p-3`}>
            <div className={`text-lg font-bold ${color}`}>{value}</div>
            <div className="text-xs text-gray-500">{label}</div>
          </div>
        ))}
      </div>

      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search by code, title, or description..."
            className="w-full pl-9 pr-4 py-2 text-sm border border-gray-300 rounded-lg bg-white focus:ring-2 focus:ring-amber-500" />
        </div>
        <div className="flex gap-2">
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
            className="px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white focus:ring-2 focus:ring-amber-500">
            {STATUS_FILTERS.map(s => <option key={s} value={s}>{s === 'all' ? 'All Status' : s.replace(/_/g, ' ')}</option>)}
          </select>
          <select value={sortBy} onChange={e => setSortBy(e.target.value)}
            className="px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white focus:ring-2 focus:ring-amber-500">
            <option value="code">By Code</option>
            <option value="status">By Status</option>
            <option value="date">By Date</option>
          </select>
        </div>
      </div>

      {/* Table */}
      {filtered.length === 0 ? (
        <EmptyState icon={Shield} title={search ? 'No matching requirements' : 'No requirements yet'}
          description={search ? 'Try different search or filter.' : 'Create your first requirement or use the Golden Flow.'}
          action={!search ? { label: 'Create Requirement', onClick: () => setShowCreate(true) } : undefined} />
      ) : (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="divide-y divide-gray-100">
            {filtered.map((req) => (
              <div key={req.id} className="px-5 py-3.5 hover:bg-gray-50 transition-colors group">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <code className="text-xs font-mono text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded">{req.code}</code>
                      <span className="text-sm font-medium text-gray-900">{req.title}</span>
                      {req.baseline_approved && <CheckCircle2 size={14} className="text-emerald-500 flex-shrink-0" title="Baseline approved" />}
                    </div>
                    {req.description && (
                      <p className="text-xs text-gray-500 line-clamp-2 mt-0.5">{req.description}</p>
                    )}
                    <div className="flex items-center gap-3 mt-1.5 text-xs text-gray-400">
                      <span>v{req.revision}</span>
                      <span>{req.created_by}</span>
                      <span>{new Date(req.updated_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <StatusBadge status={req.status} />
                    {req.status === 'draft' && (
                      <button title="Edit"
                        className="p-1 text-gray-300 hover:text-amber-600 opacity-0 group-hover:opacity-100 transition">
                        <Edit3 size={14} />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div className="px-5 py-2 bg-gray-50 border-t border-gray-100 text-xs text-gray-400">
            {filtered.length} of {requirements.length} requirements
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setShowCreate(false)} />
          <div className="relative bg-white rounded-xl shadow-2xl max-w-lg w-full mx-4 p-6 z-10">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">New Requirement</h2>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Code</label>
                <input required value={newReq.code} onChange={e => setNewReq({ ...newReq, code: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-amber-500 font-mono"
                  placeholder="REQ-001" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
                <input required value={newReq.title} onChange={e => setNewReq({ ...newReq, title: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-amber-500"
                  placeholder="Requirement title..." />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea rows={3} value={newReq.description} onChange={e => setNewReq({ ...newReq, description: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-amber-500 resize-none" />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setShowCreate(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50">Cancel</button>
                <button type="submit" disabled={creating}
                  className="px-4 py-2 text-sm font-medium text-white bg-amber-600 rounded-lg hover:bg-amber-700 disabled:opacity-50 flex items-center gap-1.5">
                  {creating && <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />}
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Multi-AI Analysis for requirements */}
      {requirements.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 card-premium">
          <MultiAIAnalysis
            content={requirements.map(r => `[${r.code}] ${r.title}\n${r.description || ''}`).join('\n\n')}
            mode="requirement"
            label="Analyze Requirements with Multiple AIs"
          />
        </div>
      )}
    </div>
  );
}
