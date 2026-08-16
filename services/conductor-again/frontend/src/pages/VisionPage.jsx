import { useEffect, useState } from 'react';
import { BookOpen, Plus, Clock, GitBranch, Eye, ChevronDown, ChevronRight, History } from 'lucide-react';
import { toast } from 'sonner';
import { listVisions, createVision } from '../api/client';
import { CardSkeleton } from '../components/PageSkeleton';
import EmptyState from '../components/EmptyState';
import MultiAIAnalysis from '../components/MultiAIAnalysis';

export default function VisionPage({ slug }) {
  const [loading, setLoading] = useState(true);
  const [visions, setVisions] = useState([]);
  const [showInput, setShowInput] = useState(false);
  const [content, setContent] = useState('');
  const [saving, setSaving] = useState(false);
  const [expandedRev, setExpandedRev] = useState(null);
  const [compareMode, setCompareMode] = useState(false);
  const [compareA, setCompareA] = useState(null);
  const [compareB, setCompareB] = useState(null);

  const load = async () => {
    try {
      setVisions(await listVisions(slug));
    } catch { toast.error('Failed to load visions'); } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [slug]);

  const handleSave = async (e) => {
    e.preventDefault();
    if (!content.trim()) return;
    setSaving(true);
    try {
      await createVision(slug, content.trim());
      toast.success('Vision saved');
      setContent('');
      setShowInput(false);
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed');
    } finally { setSaving(false); }
  };

  if (loading) return <CardSkeleton count={3} />;

  const selectedA = visions.find(v => v.id === compareA);
  const selectedB = visions.find(v => v.id === compareB);

  return (
    <div className="page-shell py-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
            <BookOpen size={22} className="text-amber-600" />
            Vision
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Immutable revision history — every version is preserved and traceable.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setCompareMode(!compareMode)}
            className={`inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg transition ${
              compareMode ? 'bg-amber-100 text-amber-700' : 'text-gray-600 border border-gray-300 hover:bg-gray-50'
            }`}
          >
            <GitBranch size={16} />
            {compareMode ? 'Exit Compare' : 'Compare'}
          </button>
          <button
            onClick={() => setShowInput(true)}
            className="inline-flex items-center gap-1.5 px-3 py-2 bg-amber-600 text-white text-sm font-medium rounded-lg hover:bg-amber-700 transition"
          >
            <Plus size={16} /> New Revision
          </button>
        </div>
      </div>

      {/* Compare mode */}
      {compareMode && visions.length >= 2 && (
        <div className="bg-white border border-amber-200 rounded-xl p-4">
          <div className="flex items-center gap-4 mb-3">
            <select value={compareA || ''} onChange={e => setCompareA(e.target.value)}
              className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white">
              <option value="">Select Revision A...</option>
              {visions.map(v => <option key={v.id} value={v.id}>Revision {v.revision} — {new Date(v.created_at).toLocaleDateString()}</option>)}
            </select>
            <span className="text-gray-400 text-sm">vs</span>
            <select value={compareB || ''} onChange={e => setCompareB(e.target.value)}
              className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white">
              <option value="">Select Revision B...</option>
              {visions.filter(v => v.id !== compareA).map(v => <option key={v.id} value={v.id}>Revision {v.revision} — {new Date(v.created_at).toLocaleDateString()}</option>)}
            </select>
          </div>
          {selectedA && selectedB && (
            <div className="grid grid-cols-2 gap-4">
              <div className="p-3 bg-gray-50 rounded-lg">
                <div className="text-xs font-medium text-gray-500 mb-1">Revision {selectedA.revision} — {selectedA.created_by}</div>
                <p className="text-sm text-gray-700 whitespace-pre-wrap">{selectedA.content}</p>
              </div>
              <div className="p-3 bg-amber-50 rounded-lg">
                <div className="text-xs font-medium text-amber-700 mb-1">Revision {selectedB.revision} — {selectedB.created_by}</div>
                <p className="text-sm text-gray-700 whitespace-pre-wrap">{selectedB.content}</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* New revision input */}
      {showInput && (
        <form onSubmit={handleSave} className="bg-white border border-amber-200 rounded-xl p-5 card-premium">
          <textarea
            value={content}
            onChange={e => setContent(e.target.value)}
            rows={5}
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-amber-500 resize-none"
            placeholder="Describe the business vision for this project..."
            autoFocus
          />
          <div className="flex justify-between items-center mt-3">
            <span className="text-xs text-gray-400">
              New revisions are immutable once saved.
            </span>
            <div className="flex gap-2">
              <button type="button" onClick={() => { setShowInput(false); setContent(''); }}
                className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:text-gray-900">Cancel</button>
              <button type="submit" disabled={saving || !content.trim()}
                className="px-3 py-1.5 text-xs font-medium text-white bg-amber-600 rounded-lg hover:bg-amber-700 disabled:opacity-50 flex items-center gap-1.5">
                {saving && <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />}
                Save Revision {visions.length > 0 ? `#${visions[0].revision + 1}` : '#1'}
              </button>
            </div>
          </div>
        </form>
      )}

      {/* Revision timeline */}
      {visions.length === 0 ? (
        <EmptyState icon={BookOpen} title="No vision defined"
          description="Start by defining the business vision for this project."
          action={{ label: 'Add Vision', onClick: () => setShowInput(true) }} />
      ) : (
        <div className="space-y-0">
          {visions.map((v, i) => (
            <div key={v.id} className="relative pl-8">
              {/* Timeline connector */}
              {i < visions.length - 1 && (
                <div className="absolute left-[15px] top-10 bottom-0 w-0.5 bg-amber-200" />
              )}
              {/* Timeline dot */}
              <div className={`absolute left-[7px] top-5 w-[18px] h-[18px] rounded-full border-2 flex items-center justify-center ${
                i === 0 ? 'bg-amber-100 border-amber-500' : 'bg-white border-gray-300'
              }`}>
                {i === 0 && <div className="w-2 h-2 rounded-full bg-amber-500" />}
              </div>

              <div className={`bg-white border rounded-xl p-5 mb-2 card-premium ${
                i === 0 ? 'border-amber-300' : 'border-gray-200'
              }`}>
                <div className="flex items-center justify-between mb-2 cursor-pointer"
                  onClick={() => setExpandedRev(expandedRev === v.id ? null : v.id)}>
                  <div className="flex items-center gap-3">
                    <span className={`text-sm font-bold ${i === 0 ? 'text-amber-700' : 'text-gray-500'}`}>
                      Revision {v.revision}
                    </span>
                    {i === 0 && (
                      <span className="text-[10px] font-medium bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded-full">LATEST</span>
                    )}
                    <span className="text-xs text-gray-400 flex items-center gap-1">
                      <Clock size={11} /> {new Date(v.created_at).toLocaleDateString()}
                    </span>
                    <span className="text-xs text-gray-400">· {v.created_by}</span>
                  </div>
                  <button className="p-1 text-gray-400 hover:text-gray-600">
                    {expandedRev === v.id ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                  </button>
                </div>
                {(expandedRev === v.id || i === 0) && (
                  <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{v.content}</p>
                )}
                {expandedRev !== v.id && i !== 0 && (
                  <p className="text-sm text-gray-500 line-clamp-2">{v.content}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Multi-AI Analysis for latest vision */}
      {visions.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-5 card-premium">
          <MultiAIAnalysis
            content={visions[0].content}
            mode="vision"
            label="Analyze with Multiple AIs"
          />
        </div>
      )}
    </div>
  );
}
