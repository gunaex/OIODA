import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  listItems,
  createItem,
  deleteItem,
  exportUrl,
  listSuggestedDocuments,
  addDocumentFromTemplate,
} from '../api/client'
import StatusBadge from '../components/StatusBadge.jsx'

const PHASES = ['UR', 'DR', 'DN', 'PU', 'ST', 'UT', 'TR', 'IP', 'MA']
const STATUSES = ['Draft', 'InReview', 'Confirmed', 'Rejected']

const emptyForm = { doc_code: '', title: '', phase: '', doc_type: '', owner: '' }

export default function DocumentList() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [filters, setFilters] = useState({ phase: '', status: '' })
  const [suggested, setSuggested] = useState([])
  const [addingCode, setAddingCode] = useState(null)

  const load = () => {
    setLoading(true)
    setLoadError(null)
    listItems(slug, 'documents')
      .then(setItems)
      .catch(() => setLoadError('Could not load documents — the backend may be unreachable.'))
      .finally(() => setLoading(false))
    listSuggestedDocuments(slug)
      .then(setSuggested)
      .catch(() => {}) // non-critical — the suggestions panel just stays empty
  }

  useEffect(load, [slug])

  const addSuggested = async (docCode) => {
    setAddingCode(docCode)
    try {
      await addDocumentFromTemplate(slug, docCode)
      load()
    } finally {
      setAddingCode(null)
    }
  }

  const filtered = useMemo(
    () =>
      items.filter(
        (i) => (!filters.phase || i.phase === filters.phase) && (!filters.status || i.status === filters.status),
      ),
    [items, filters],
  )

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const save = async () => {
    if (!form.title.trim()) return
    await createItem(slug, 'documents', form)
    setAdding(false)
    setForm(emptyForm)
    load()
  }

  const remove = async (id, e) => {
    e.stopPropagation()
    if (!confirm('Delete this document?')) return
    await deleteItem(slug, 'documents', id)
    load()
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Documents</h2>
        <div className="flex flex-wrap items-center gap-3">
          <a
            href={exportUrl(slug, 'documents')}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
          >
            Export
          </a>
          <button
            onClick={() => setAdding((v) => !v)}
            className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
          >
            + Add Document
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 mb-4">
        <select
          value={filters.phase}
          onChange={(e) => setFilters((f) => ({ ...f, phase: e.target.value }))}
          className="text-sm border border-gray-300 rounded-md px-2 py-1.5"
        >
          <option value="">All Phases</option>
          {PHASES.map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
        <select
          value={filters.status}
          onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
          className="text-sm border border-gray-300 rounded-md px-2 py-1.5"
        >
          <option value="">All Statuses</option>
          {STATUSES.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </div>

      {suggested.length > 0 && (
        <div className="mb-4 p-4 bg-indigo-50/50 border border-indigo-100 rounded-lg">
          <div className="text-xs font-semibold text-indigo-700 uppercase mb-2">
            Suggested (Optional) Documents
          </div>
          <ul className="flex flex-wrap gap-2">
            {suggested.map((t) => (
              <li key={t.doc_code}>
                <button
                  onClick={() => addSuggested(t.doc_code)}
                  disabled={addingCode === t.doc_code}
                  className="px-2.5 py-1 text-xs bg-white border border-indigo-200 rounded-full hover:bg-indigo-100 disabled:opacity-50"
                >
                  + {t.doc_name} ({t.phase_name})
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {adding && (
        <div className="mb-4 p-4 bg-white border border-gray-200 rounded-lg flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Doc Code</label>
            <input value={form.doc_code} onChange={set('doc_code')} className="w-28 border border-gray-300 rounded px-2 py-1 text-sm" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Title</label>
            <input value={form.title} onChange={set('title')} className="border border-gray-300 rounded px-2 py-1 text-sm" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Phase</label>
            <select value={form.phase} onChange={set('phase')} className="border border-gray-300 rounded px-2 py-1 text-sm">
              <option value="">-</option>
              {PHASES.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Doc Type</label>
            <input value={form.doc_type} onChange={set('doc_type')} placeholder="e.g. URS" className="w-28 border border-gray-300 rounded px-2 py-1 text-sm" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Owner</label>
            <input value={form.owner} onChange={set('owner')} className="w-28 border border-gray-300 rounded px-2 py-1 text-sm" />
          </div>
          <div className="flex gap-2">
            <button onClick={save} className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700">
              Save
            </button>
            <button
              onClick={() => {
                setAdding(false)
                setForm(emptyForm)
              }}
              className="px-3 py-1.5 text-sm text-gray-600 border border-gray-200 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="bg-white border border-gray-200 rounded-lg overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-gray-600 text-left">
            <tr>
              <th className="px-3 py-2">Code</th>
              <th className="px-3 py-2">Title</th>
              <th className="px-3 py-2">Phase</th>
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2">Owner</th>
              <th className="px-3 py-2">Version</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} className="px-3 py-4 text-center text-gray-400">
                  Loading…
                </td>
              </tr>
            ) : loadError ? (
              <tr>
                <td colSpan={8} className="px-3 py-4 text-center text-red-600">
                  {loadError}{' '}
                  <button onClick={load} className="underline font-medium">
                    Retry
                  </button>
                </td>
              </tr>
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-3 py-4 text-center text-gray-400">
                  No documents yet.
                </td>
              </tr>
            ) : (
              filtered.map((item) => (
                <tr
                  key={item.id}
                  onClick={() => navigate(`/${slug}/documents/${item.id}`)}
                  className="border-t border-gray-100 hover:bg-gray-50 cursor-pointer"
                >
                  <td className="px-3 py-2">{item.doc_code}</td>
                  <td className="px-3 py-2 font-medium text-gray-900">{item.title}</td>
                  <td className="px-3 py-2">{item.phase}</td>
                  <td className="px-3 py-2">{item.doc_type}</td>
                  <td className="px-3 py-2">{item.owner}</td>
                  <td className="px-3 py-2">v{item.version}</td>
                  <td className="px-3 py-2">
                    <StatusBadge status={item.status} />
                  </td>
                  <td className="px-3 py-2 text-right whitespace-nowrap">
                    <button onClick={(e) => remove(item.id, e)} className="text-red-600 hover:underline">
                      Delete
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
