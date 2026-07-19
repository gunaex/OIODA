import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useOutletContext, useParams } from 'react-router-dom'
import { listItems, createItem, updateItem, deleteItem, cloneItem, openOrCreateWhiteboard } from '../api/client'
import ImportExportBar from '../components/ImportExportBar.jsx'
import StatusBadge from '../components/StatusBadge.jsx'

const TYPES = ['Functional', 'Non-Functional']
const PHASES = ['UR', 'DR', 'DN', 'PU', 'ST', 'UT', 'TR', 'IP', 'MA']
const STATUSES = ['Draft', 'Confirmed', 'InProgress', 'Done']
const PRIORITIES = ['Must', 'Should', 'Could', "Won't"]
const SCOPE_CLASSES = ['Core', 'Core/Overlap', 'Extended']
const COMPLEXITIES = ['Low', 'Medium', 'High']
const PERFORMANCE_CLASSES = ['Batch/Async', 'Transactional', 'Calculation/CRUD']
const PD_FIELDS = ['pd_ba', 'pd_ux', 'pd_fe', 'pd_be', 'pd_int_data', 'pd_qa', 'pd_devops']
const PD_LABELS = { pd_ba: 'BA', pd_ux: 'UX', pd_fe: 'FE', pd_be: 'BE', pd_int_data: 'Int/Data', pd_qa: 'QA', pd_devops: 'DevOps' }

const emptyForm = {
  function_code: '',
  name: '',
  description: '',
  type: '',
  phase: '',
  owner: '',
  status: 'Draft',
  module: '',
  priority: '',
  scope_class: '',
  complexity: '',
  pd_ba: '',
  pd_ux: '',
  pd_fe: '',
  pd_be: '',
  pd_int_data: '',
  pd_qa: '',
  pd_devops: '',
  performance_class: '',
  target_option_a: '',
  target_option_b: '',
  target_option_c: '',
  performance_note: '',
  price_thb: '',
  commercial_note: '',
}

export default function FunctionList() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const { project } = useOutletContext() ?? {}
  const isEstimate = project?.project_type === 'estimate'

  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [adding, setAdding] = useState(false)
  const [filters, setFilters] = useState({ type: '', phase: '', status: '' })

  const load = () => {
    setLoading(true)
    setLoadError(null)
    listItems(slug, 'functions')
      .then(setItems)
      .catch(() => setLoadError('Could not load functions — the backend may be unreachable.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [slug])

  const filtered = useMemo(
    () =>
      items.filter(
        (i) =>
          (!filters.type || i.type === filters.type) &&
          (!filters.phase || i.phase === filters.phase) &&
          (!filters.status || i.status === filters.status),
      ),
    [items, filters],
  )

  const startEdit = (item) => {
    setEditingId(item.id)
    setForm({ ...emptyForm, ...item })
    setAdding(false)
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
    const payload = { ...form }
    for (const key of [...PD_FIELDS, 'price_thb']) {
      payload[key] = payload[key] === '' ? null : Number(payload[key])
    }
    if (adding) {
      await createItem(slug, 'functions', payload)
    } else {
      await updateItem(slug, 'functions', editingId, payload)
    }
    cancel()
    load()
  }

  const remove = async (id) => {
    if (!confirm('Delete this function?')) return
    await deleteItem(slug, 'functions', id)
    load()
  }

  const clone = async (id) => {
    await cloneItem(slug, 'functions', id)
    load()
  }

  const openWhiteboard = async (item) => {
    const boardId = await openOrCreateWhiteboard(slug, 'function', item.id, `Whiteboard: ${item.name}`)
    navigate(`/${slug}/whiteboards/${boardId}`)
  }

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Function / Requirement List</h2>
        <div className="flex flex-wrap items-center gap-3">
          <ImportExportBar slug={slug} entity="functions" onImported={load} />
          <button
            onClick={startAdd}
            className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
          >
            + Add Function
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 mb-4">
        <select
          value={filters.type}
          onChange={(e) => setFilters((f) => ({ ...f, type: e.target.value }))}
          className="text-sm border border-gray-300 rounded-md px-2 py-1.5"
        >
          <option value="">All Types</option>
          {TYPES.map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
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

      <div className="bg-white border border-gray-200 rounded-lg overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-gray-600 text-left">
            <tr>
              <th className="px-3 py-2">Code</th>
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Module</th>
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2">Phase</th>
              <th className="px-3 py-2">Owner</th>
              <th className="px-3 py-2">Status</th>
              {isEstimate && <th className="px-3 py-2">Priority</th>}
              {isEstimate && <th className="px-3 py-2">Complexity</th>}
              {isEstimate && <th className="px-3 py-2">PD Total</th>}
              {isEstimate && <th className="px-3 py-2">Price (THB)</th>}
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {adding && (
              <EditRow form={form} set={set} onSave={save} onCancel={cancel} isEstimate={isEstimate} />
            )}
            {loading ? (
              <tr>
                <td colSpan={isEstimate ? 12 : 8} className="px-3 py-4 text-center text-gray-400">
                  Loading…
                </td>
              </tr>
            ) : loadError ? (
              <tr>
                <td colSpan={isEstimate ? 12 : 8} className="px-3 py-4 text-center text-red-600">
                  {loadError}{' '}
                  <button onClick={load} className="underline font-medium">
                    Retry
                  </button>
                </td>
              </tr>
            ) : filtered.length === 0 && !adding ? (
              <tr>
                <td colSpan={isEstimate ? 12 : 8} className="px-3 py-4 text-center text-gray-400">
                  No functions yet.
                </td>
              </tr>
            ) : (
              filtered.map((item) =>
                editingId === item.id ? (
                  <EditRow
                    key={item.id}
                    form={form}
                    set={set}
                    onSave={save}
                    onCancel={cancel}
                    isEstimate={isEstimate}
                  />
                ) : (
                  <tr key={item.id} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-3 py-2">{item.function_code}</td>
                    <td className="px-3 py-2 font-medium text-gray-900">{item.name}</td>
                    <td className="px-3 py-2">{item.module}</td>
                    <td className="px-3 py-2">{item.type}</td>
                    <td className="px-3 py-2">{item.phase}</td>
                    <td className="px-3 py-2">{item.owner}</td>
                    <td className="px-3 py-2">
                      <StatusBadge status={item.status} />
                    </td>
                    {isEstimate && <td className="px-3 py-2">{item.priority}</td>}
                    {isEstimate && <td className="px-3 py-2">{item.complexity}</td>}
                    {isEstimate && <td className="px-3 py-2">{item.pd_total ?? ''}</td>}
                    {isEstimate && <td className="px-3 py-2">{item.price_thb ?? ''}</td>}
                    <td className="px-3 py-2 text-right whitespace-nowrap">
                      <button
                        onClick={() => startEdit(item)}
                        className="text-indigo-600 hover:underline mr-3"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => clone(item.id)}
                        className="text-gray-500 hover:underline mr-3"
                      >
                        Clone
                      </button>
                      <button
                        onClick={() => openWhiteboard(item)}
                        className="text-gray-500 hover:underline mr-3"
                      >
                        Whiteboard
                      </button>
                      <button
                        onClick={() => remove(item.id)}
                        className="text-red-600 hover:underline"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ),
              )
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function EditRow({ form, set, onSave, onCancel, isEstimate }) {
  const colSpan = isEstimate ? 12 : 8
  const pdTotalPreview = PD_FIELDS.reduce((sum, k) => sum + (Number(form[k]) || 0), 0)

  return (
    <>
      <tr className="border-t border-gray-100 bg-indigo-50/40">
        <td className="px-2 py-1.5">
          <input
            value={form.function_code || ''}
            onChange={set('function_code')}
            className="w-24 border border-gray-300 rounded px-2 py-1 text-sm"
          />
        </td>
        <td className="px-2 py-1.5">
          <input
            value={form.name || ''}
            onChange={set('name')}
            placeholder="Name"
            className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
          />
        </td>
        <td className="px-2 py-1.5">
          <input
            value={form.module || ''}
            onChange={set('module')}
            placeholder="Module"
            className="w-28 border border-gray-300 rounded px-2 py-1 text-sm"
          />
        </td>
        <td className="px-2 py-1.5">
          <select
            value={form.type || ''}
            onChange={set('type')}
            className="border border-gray-300 rounded px-2 py-1 text-sm"
          >
            <option value="">-</option>
            {TYPES.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </td>
        <td className="px-2 py-1.5">
          <select
            value={form.phase || ''}
            onChange={set('phase')}
            className="border border-gray-300 rounded px-2 py-1 text-sm"
          >
            <option value="">-</option>
            {PHASES.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </td>
        <td className="px-2 py-1.5">
          <input
            value={form.owner || ''}
            onChange={set('owner')}
            className="w-24 border border-gray-300 rounded px-2 py-1 text-sm"
          />
        </td>
        <td className="px-2 py-1.5">
          <select
            value={form.status || ''}
            onChange={set('status')}
            className="border border-gray-300 rounded px-2 py-1 text-sm"
          >
            {STATUSES.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </td>
        {isEstimate && (
          <>
            <td className="px-2 py-1.5">
              <select
                value={form.priority || ''}
                onChange={set('priority')}
                className="border border-gray-300 rounded px-2 py-1 text-sm"
              >
                <option value="">-</option>
                {PRIORITIES.map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </td>
            <td className="px-2 py-1.5">
              <select
                value={form.complexity || ''}
                onChange={set('complexity')}
                className="border border-gray-300 rounded px-2 py-1 text-sm"
              >
                <option value="">-</option>
                {COMPLEXITIES.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </td>
            <td className="px-2 py-1.5 text-gray-500">{pdTotalPreview || ''}</td>
            <td className="px-2 py-1.5">
              <input
                type="number"
                value={form.price_thb ?? ''}
                onChange={set('price_thb')}
                className="w-24 border border-gray-300 rounded px-2 py-1 text-sm"
              />
            </td>
          </>
        )}
        <td className="px-2 py-1.5 text-right whitespace-nowrap">
          <button onClick={onSave} className="text-green-600 hover:underline mr-3">
            Save
          </button>
          <button onClick={onCancel} className="text-gray-500 hover:underline">
            Cancel
          </button>
        </td>
      </tr>
      {isEstimate && (
        <tr className="bg-indigo-50/20">
          <td colSpan={colSpan} className="px-4 py-3">
            <div className="text-xs font-semibold text-gray-500 uppercase mb-2">
              Estimate & Pricing
            </div>
            <div className="flex flex-wrap gap-3 items-end">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Scope Class</label>
                <select
                  value={form.scope_class || ''}
                  onChange={set('scope_class')}
                  className="border border-gray-300 rounded px-2 py-1 text-sm"
                >
                  <option value="">-</option>
                  {SCOPE_CLASSES.map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </div>
              {PD_FIELDS.map((f) => (
                <div key={f}>
                  <label className="block text-xs text-gray-500 mb-1">{PD_LABELS[f]} (PD)</label>
                  <input
                    type="number"
                    step="0.5"
                    value={form[f] ?? ''}
                    onChange={set(f)}
                    className="w-16 border border-gray-300 rounded px-2 py-1 text-sm"
                  />
                </div>
              ))}
              <div>
                <label className="block text-xs text-gray-500 mb-1">Performance Class</label>
                <select
                  value={form.performance_class || ''}
                  onChange={set('performance_class')}
                  className="border border-gray-300 rounded px-2 py-1 text-sm"
                >
                  <option value="">-</option>
                  {PERFORMANCE_CLASSES.map((p) => (
                    <option key={p}>{p}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Target A</label>
                <input
                  value={form.target_option_a || ''}
                  onChange={set('target_option_a')}
                  className="w-24 border border-gray-300 rounded px-2 py-1 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Target B</label>
                <input
                  value={form.target_option_b || ''}
                  onChange={set('target_option_b')}
                  className="w-24 border border-gray-300 rounded px-2 py-1 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Target C</label>
                <input
                  value={form.target_option_c || ''}
                  onChange={set('target_option_c')}
                  className="w-24 border border-gray-300 rounded px-2 py-1 text-sm"
                />
              </div>
              <div className="flex-1 min-w-[180px]">
                <label className="block text-xs text-gray-500 mb-1">Performance Note</label>
                <input
                  value={form.performance_note || ''}
                  onChange={set('performance_note')}
                  className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                />
              </div>
              <div className="flex-1 min-w-[180px]">
                <label className="block text-xs text-gray-500 mb-1">Commercial Note</label>
                <input
                  value={form.commercial_note || ''}
                  onChange={set('commercial_note')}
                  className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                />
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
