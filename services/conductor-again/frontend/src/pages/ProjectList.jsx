import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Zap, Plus, FolderOpen, ArrowRight, Search } from 'lucide-react';
import { toast } from 'sonner';
import { listProjects, createProject } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import EmptyState from '../components/EmptyState';
import { CardSkeleton } from '../components/PageSkeleton';
import ConfirmDialog from '../components/ConfirmDialog';
import StatusBadge from '../components/StatusBadge';

export default function ProjectList() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  // Create modal state
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newSlug, setNewSlug] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [creating, setCreating] = useState(false);

  const fetchProjects = async () => {
    try {
      const data = await listProjects();
      setProjects(data);
    } catch {
      toast.error('Failed to load projects');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchProjects(); }, []);

  const filtered = projects.filter((p) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return p.name.toLowerCase().includes(q) || p.slug.toLowerCase().includes(q);
  });

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newName.trim() || !newSlug.trim()) return;
    setCreating(true);
    try {
      const project = await createProject({
        name: newName.trim(),
        slug: newSlug.trim().toLowerCase().replace(/\s+/g, '-'),
        description: newDesc.trim(),
      });
      toast.success('Project created');
      setShowCreate(false);
      setNewName(''); setNewSlug(''); setNewDesc('');
      navigate(`/${project.slug}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to create project');
    } finally {
      setCreating(false);
    }
  };

  if (loading) return <CardSkeleton count={6} />;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-white/85 backdrop-blur-md border-b border-gray-200">
        <div className="px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-amber-100 flex items-center justify-center">
              <Zap size={18} className="text-amber-600" />
            </div>
            <span className="text-sm font-semibold text-gray-900">
              Conductor <span className="text-amber-600">Again</span>
            </span>
          </div>
        </div>
      </header>

      <div className="page-shell py-6 max-w-6xl mx-auto">
        {/* Hero */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
            <FolderOpen size={26} className="text-amber-600" />
            Projects
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage your governed projects — each project has its own Vision, Requirements, Skills, and AI routing policies.
          </p>
        </div>

        {/* Toolbar */}
        <div className="flex flex-col sm:flex-row gap-3 mb-6">
          <div className="relative flex-1 max-w-sm">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search projects…"
              className="w-full pl-9 pr-4 py-2 text-sm border border-gray-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 transition"
            />
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-amber-600 text-white text-sm font-medium rounded-lg hover:bg-amber-700 transition focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2"
          >
            <Plus size={16} />
            New Project
          </button>
        </div>

        {/* Project Grid */}
        {filtered.length === 0 ? (
          <EmptyState
            icon={FolderOpen}
            title={search ? 'No matching projects' : 'No projects yet'}
            description={search ? 'Try a different search term.' : 'Create your first project to start orchestrating.'}
            action={!search ? { label: 'Create Project', onClick: () => setShowCreate(true) } : undefined}
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {filtered.map((p) => (
              <Link
                key={p.id}
                to={`/${p.slug}`}
                className="group bg-white border border-gray-200 rounded-xl p-5 hover:border-amber-300 hover:shadow-md transition-all card-premium"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="w-10 h-10 rounded-lg bg-amber-50 flex items-center justify-center group-hover:bg-amber-100 transition-colors">
                    <FolderOpen size={20} className="text-amber-600" />
                  </div>
                  <StatusBadge status={p.status} />
                </div>
                <h3 className="font-semibold text-gray-900 group-hover:text-amber-700 transition-colors">
                  {p.name}
                </h3>
                {p.description && (
                  <p className="mt-1 text-sm text-gray-500 line-clamp-2">{p.description}</p>
                )}
                <div className="mt-4 flex items-center justify-between">
                  <code className="text-xs text-gray-400 bg-gray-50 px-2 py-0.5 rounded">{p.slug}</code>
                  <ArrowRight size={14} className="text-gray-300 group-hover:text-amber-500 transition-colors" />
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setShowCreate(false)} />
          <div className="relative bg-white rounded-xl shadow-2xl max-w-md w-full mx-4 p-6 z-10">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">New Project</h2>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label htmlFor="projName" className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input
                  id="projName"
                  type="text"
                  required
                  value={newName}
                  onChange={(e) => { setNewName(e.target.value); setNewSlug(e.target.value.toLowerCase().replace(/\s+/g, '-')); }}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 transition"
                  placeholder="My Project"
                />
              </div>
              <div>
                <label htmlFor="projSlug" className="block text-sm font-medium text-gray-700 mb-1">Slug</label>
                <input
                  id="projSlug"
                  type="text"
                  required
                  value={newSlug}
                  onChange={(e) => setNewSlug(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg bg-gray-50 font-mono focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 transition"
                  placeholder="my-project"
                />
              </div>
              <div>
                <label htmlFor="projDesc" className="block text-sm font-medium text-gray-700 mb-1">Description (optional)</label>
                <textarea
                  id="projDesc"
                  rows={2}
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 transition resize-none"
                  placeholder="Brief description…"
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating || !newName.trim() || !newSlug.trim()}
                  className="px-4 py-2 text-sm font-medium text-white bg-amber-600 rounded-lg hover:bg-amber-700 disabled:opacity-50 transition flex items-center gap-2"
                >
                  {creating && <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />}
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
