import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { listAllocations, createAllocation, updateAllocation, deleteAllocation, listResources } from '../api/client'

const emptyForm = { resource_id: '', allocation_percent: 100, start_date: '', end_date: '', note: '' }

export default function ProjectAllocations() {
  const { slug } = useParams()
  const [allocations, setAllocations] = useState([])
  const [resources, setResources] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState(emptyForm)

  const load = () => {
    setLoading(true)
    setLoadError(null)
    Promise.all([listAllocations(slug), listResources()])
      .then(([a, r]) => {
        setAllocations(a)
        setResources(r)
      })
      .catch(() => setLoadError('Could not load allocations — the backend may be unreachable.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [slug])

  const resourceName = (id) => resources.find((r) => r.id === id)?.name || `#${id}`

  const startEdit = (a) => {
    setEditingId(a.id)
    setAdding(false)
    setForm({ ...emptyForm, ...a, note: a.note || '' })
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
    if (!form.resource_id || !form.start_date || !form.end_date) return
    const payload = {
      resource_id: Number(form.resource_id),
      allocation_percent: Number(form.allocation_percent),
      start_date: form.start_date,
      end_date: form.end_date,
      note: form.note || null,
    }
    if (adding) {
      await createAllocation(slug, payload)
    } else {
      await updateAllocation(slug, editingId, payload)
    }
    cancel()
    load()
  }

  const remove = async (id) => {
    if (!confirm('Delete this allocation?')) return
    await deleteAllocation(slug, id)
    load()
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Resource Allocations</h2>
        {!adding && editingId === null && (
          <button
            onClick={startAdd}
            className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
          >
            + Allocate Resource
          </button>
        )}
      </div>

      <div className="bg-white border border-gray-200 rounded-lg">
        {(adding || editingId !== null) && (
          <div className="flex flex-wrap gap-2 px-4 py-3 border-b border-gray-100 bg-gray-50">
            <select
              value={form.resource_id}
              onChange={(e) => setForm({ ...form, resource_id: e.target.value })}
              className="px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              <option value="">Select resource…</option>
              {resources.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name} {r.role ? `(${r.role})` : ''}
                </option>
              ))}
            </select>
            <input
              type="number"
              min="0"
              max="100"
              value={form.allocation_percent}
              onChange={(e) => setForm({ ...form, allocation_percent: e.target.value })}
              placeholder="%"
              className="w-20 px-3 py-2 border border-gray-300 rounded-md text-sm"
            />
            <input
              type="date"
              value={form.start_date}
              onChange={(e) => setForm({ ...form, start_date: e.target.value })}
              className="px-3 py-2 border border-gray-300 rounded-md text-sm"
            />
            <input
              type="date"
              value={form.end_date}
              onChange={(e) => setForm({ ...form, end_date: e.target.value })}
              className="px-3 py-2 border border-gray-300 rounded-md text-sm"
            />
            <input
              value={form.note}
              onChange={(e) => setForm({ ...form, note: e.target.value })}
              placeholder="Note (optional)"
              className="flex-1 min-w-[140px] px-3 py-2 border border-gray-300 rounded-md text-sm"
            />
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
          ) : allocations.length === 0 ? (
            <p className="px-4 py-4 text-center text-gray-400 text-sm">
              No resources allocated to this project yet.
            </p>
          ) : (
            allocations.map((a) => (
              <div key={a.id} className="flex items-center justify-between gap-3 px-4 py-3">
                <div className="min-w-0">
                  <p className="text-sm text-gray-900">
                    {resourceName(a.resource_id)} — {a.allocation_percent}%
                  </p>
                  <p className="text-xs text-gray-400">
                    {a.start_date} → {a.end_date}
                    {a.note ? ` · ${a.note}` : ''}
                  </p>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <button onClick={() => startEdit(a)} className="text-sm text-indigo-600 hover:underline">
                    Edit
                  </button>
                  <button onClick={() => remove(a.id)} className="text-sm text-red-600 hover:underline">
                    Delete
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
