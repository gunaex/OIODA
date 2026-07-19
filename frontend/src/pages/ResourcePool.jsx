import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { listResources, createResource, updateResource, deleteResource } from '../api/client'
import UserBadge from '../components/UserBadge.jsx'
import UtilizationHeatmap from '../components/UtilizationHeatmap.jsx'

const ROLES = ['SR.Arc', 'DevSecOps', 'SEC', 'DBA', 'Dev', 'QA', 'BA', 'UX', 'DevOps']

const emptyForm = { name: '', role: '', email: '', weekly_capacity_hours: 40, active: true }

export default function ResourcePool() {
  const [resources, setResources] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState(emptyForm)

  const load = () => {
    setLoading(true)
    setLoadError(null)
    listResources()
      .then(setResources)
      .catch(() => setLoadError('Could not load resources — the backend may be unreachable.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const startEdit = (r) => {
    setEditingId(r.id)
    setAdding(false)
    setForm({ ...emptyForm, ...r })
  }

  const startAdd = () => {
    setAdding(true)
    setEditingId(null)
    setForm(emptyForm)
  }

  const cancel = () => {
    setAdding(false)
    setEditingId(null)
    setForm(emptyForm)
  }

  const save = async () => {
    if (!form.name.trim()) return
    const payload = { ...form, weekly_capacity_hours: Number(form.weekly_capacity_hours) || 40 }
    if (adding) {
      await createResource(payload)
    } else {
      await updateResource(editingId, payload)
    }
    cancel()
    load()
  }

  const remove = async (id) => {
    if (!confirm('Delete this resource? Any existing allocations will remain but point to a missing resource.')) return
    await deleteResource(id)
    load()
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10">
        <div className="flex items-center justify-between mb-6 gap-4">
          <div className="flex items-center gap-4">
            <NavLink to="/" className="text-sm text-gray-500 hover:text-gray-800">
              &larr; Dashboard
            </NavLink>
            <h1 className="text-2xl font-semibold text-gray-900">Resource Pool</h1>
          </div>
          <UserBadge />
        </div>

        <div className="bg-white border border-gray-200 rounded-lg mb-8">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <h2 className="font-medium text-gray-900">People</h2>
            {!adding && editingId === null && (
              <button
                onClick={startAdd}
                className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
              >
                + Add Resource
              </button>
            )}
          </div>

          {(adding || editingId !== null) && (
            <div className="flex flex-wrap gap-2 px-4 py-3 border-b border-gray-100 bg-gray-50">
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Name"
                className="flex-1 min-w-[140px] px-3 py-2 border border-gray-300 rounded-md text-sm"
              />
              <select
                value={form.role || ''}
                onChange={(e) => setForm({ ...form, role: e.target.value || null })}
                className="px-3 py-2 border border-gray-300 rounded-md text-sm"
              >
                <option value="">No role</option>
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
              <input
                value={form.email || ''}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="Email (optional)"
                className="px-3 py-2 border border-gray-300 rounded-md text-sm"
              />
              <input
                type="number"
                value={form.weekly_capacity_hours}
                onChange={(e) => setForm({ ...form, weekly_capacity_hours: e.target.value })}
                placeholder="Hrs/week"
                className="w-24 px-3 py-2 border border-gray-300 rounded-md text-sm"
              />
              <label className="flex items-center gap-1.5 text-sm text-gray-600 px-2">
                <input
                  type="checkbox"
                  checked={form.active}
                  onChange={(e) => setForm({ ...form, active: e.target.checked })}
                />
                Active
              </label>
              <button onClick={save} className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700">
                Save
              </button>
              <button onClick={cancel} className="px-3 py-1.5 text-sm text-gray-600 hover:underline">
                Cancel
              </button>
            </div>
          )}

          <div className="divide-y divide-gray-100">
            {loading ? (
              <p className="px-4 py-4 text-center text-gray-400 text-sm">Loading…</p>
            ) : loadError ? (
              <p className="px-4 py-4 text-center text-sm text-red-600">
                {loadError}{' '}
                <button onClick={load} className="underline font-medium">
                  Retry
                </button>
              </p>
            ) : resources.length === 0 ? (
              <p className="px-4 py-4 text-center text-gray-400 text-sm">No resources yet — add one above.</p>
            ) : (
              resources.map((r) => (
                <div key={r.id} className="flex items-center justify-between gap-3 px-4 py-3">
                  <div className="min-w-0">
                    <p className="text-sm text-gray-900">
                      {r.name} {r.role && <span className="text-xs text-gray-400 ml-1">({r.role})</span>}
                      {!r.active && <span className="text-xs text-gray-400 ml-2">(inactive)</span>}
                    </p>
                    <p className="text-xs text-gray-400">
                      {r.email || 'no email'} · {r.weekly_capacity_hours} hrs/week
                    </p>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <button onClick={() => startEdit(r)} className="text-sm text-indigo-600 hover:underline">
                      Edit
                    </button>
                    <button onClick={() => remove(r.id)} className="text-sm text-red-600 hover:underline">
                      Delete
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <UtilizationHeatmap />
      </div>
    </div>
  )
}
