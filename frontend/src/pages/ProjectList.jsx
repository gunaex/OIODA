import { useEffect, useState } from 'react'
import { useNavigate, NavLink } from 'react-router-dom'
import { listProjects, createProject, getGlobalDashboard } from '../api/client'
import UserBadge from '../components/UserBadge.jsx'
import UtilizationHeatmap from '../components/UtilizationHeatmap.jsx'
import StatusBadge from '../components/StatusBadge.jsx'
import { useAuth } from '../auth/AuthContext.jsx'

export default function ProjectList() {
  const { user } = useAuth()
  const isClientViewer = user?.role === 'client_viewer'
  const [projects, setProjects] = useState([])
  const [dashboardBySlug, setDashboardBySlug] = useState({})
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [projectType, setProjectType] = useState('simple')
  const [projectCategory, setProjectCategory] = useState('')
  const navigate = useNavigate()

  const load = () => {
    setLoading(true)
    setLoadError(null)
    Promise.all([listProjects(), getGlobalDashboard()])
      .then(([projectList, globalDashboard]) => {
        setProjects(projectList)
        setDashboardBySlug(Object.fromEntries(globalDashboard.projects.map((p) => [p.slug, p])))
      })
      .catch(() => setLoadError('Could not reach the backend. Your projects are safe — this is a connection problem, not data loss.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    setCreating(true)
    try {
      const project = await createProject(name.trim(), projectType, projectCategory || null)
      setName('')
      setProjectType('simple')
      setProjectCategory('')
      setProjects((prev) => [project, ...prev])
      navigate(`/${project.slug}/dashboard`)
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10">
        <div className="flex items-center justify-between mb-6 gap-4">
          <h1 className="text-2xl font-semibold text-gray-900">Projects</h1>
          <div className="flex items-center gap-4">
            {!isClientViewer && (
              <NavLink to="/resources" className="text-sm text-indigo-600 hover:underline">
                Resources
              </NavLink>
            )}
            <UserBadge />
          </div>
        </div>

        <form onSubmit={handleCreate} className="flex flex-col sm:flex-row gap-2 mb-8">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="New project name"
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <select
            value={projectType}
            onChange={(e) => setProjectType(e.target.value)}
            title="Project Type"
            className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="simple">Simple</option>
            <option value="estimate">Estimate-SI</option>
          </select>
          <select
            value={projectCategory}
            onChange={(e) => setProjectCategory(e.target.value)}
            title="Project Category"
            className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">No Category (skip auto-docs)</option>
            <option value="critical">Critical</option>
            <option value="non_critical">Non-Critical</option>
            <option value="ma">MA</option>
            <option value="rollout">Rollout</option>
          </select>
          <button
            type="submit"
            disabled={creating}
            className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 disabled:opacity-50"
          >
            {creating ? 'Creating…' : 'New Project'}
          </button>
        </form>

        {loading ? (
          <p className="text-gray-500 text-sm">Loading…</p>
        ) : loadError ? (
          <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-md px-4 py-3">
            <p>{loadError}</p>
            <button onClick={load} className="mt-2 text-red-800 font-medium hover:underline">
              Retry
            </button>
          </div>
        ) : projects.length === 0 ? (
          <p className="text-gray-500 text-sm">No projects yet. Create one above.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
            {projects.map((p) => {
              const summary = dashboardBySlug[p.slug]
              return (
                <button
                  key={p.id}
                  onClick={() => navigate(`/${p.slug}/dashboard`)}
                  className="text-left p-5 bg-white border border-gray-200 rounded-lg hover:shadow-md hover:border-indigo-300 transition"
                >
                  <div className="flex items-center gap-2 flex-wrap">
                    <h2 className="font-medium text-gray-900">{p.name}</h2>
                    {summary && <StatusBadge status={summary.rag} />}
                    <span className="px-1.5 py-0.5 text-[10px] uppercase tracking-wide rounded bg-gray-100 text-gray-500">
                      {p.project_type}
                    </span>
                    {p.project_category && (
                      <span className="px-1.5 py-0.5 text-[10px] uppercase tracking-wide rounded bg-indigo-50 text-indigo-600">
                        {p.project_category.replace('_', ' ')}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 mt-1">{p.slug}</p>
                  {summary && (
                    <p className="text-xs text-gray-400 mt-2">
                      {summary.overdue_task_count} overdue task(s) · {summary.open_issue_count} open issue(s)
                    </p>
                  )}
                  <p className="text-xs text-gray-400 mt-1">
                    Created {new Date(p.created_at).toLocaleDateString()}
                  </p>
                </button>
              )
            })}
          </div>
        )}

        {!isClientViewer && <UtilizationHeatmap />}
      </div>
    </div>
  )
}
