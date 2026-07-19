import { Fragment, useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { listItems, createItem, updateItem, deleteItem, cloneItem } from '../api/client'
import ImportExportBar from '../components/ImportExportBar.jsx'
import StatusBadge from '../components/StatusBadge.jsx'
import CommentsPanel from '../components/CommentsPanel.jsx'

const MY_NAME_KEY = 'pm-again:my-name'

const STATUSES = ['Todo', 'InProgress', 'Done', 'Blocked']
const PRIORITIES = ['Low', 'Med', 'High']
const PHASES = ['UR', 'DR', 'DN', 'PU', 'ST', 'UT', 'TR', 'IP', 'MA']

const emptyForm = {
  task_code: '',
  title: '',
  description: '',
  phase: '',
  owner: '',
  due_date: '',
  status: 'Todo',
  priority: 'Med',
  is_followup: false,
}

export default function TaskList() {
  const { slug } = useParams()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [tab, setTab] = useState('all')
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [adding, setAdding] = useState(false)
  const [filters, setFilters] = useState({ owner: '', status: '', phase: '' })
  const [myName, setMyName] = useState(() => localStorage.getItem(MY_NAME_KEY) || '')
  const [commentsOpenId, setCommentsOpenId] = useState(null)

  const load = () => {
    setLoading(true)
    setLoadError(null)
    listItems(slug, 'tasks')
      .then(setItems)
      .catch(() => setLoadError('Could not load tasks — the backend may be unreachable.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [slug])

  const filtered = useMemo(
    () =>
      items.filter(
        (i) =>
          (tab === 'all' || (tab === 'followup' && i.is_followup) || (tab === 'mine' && i.owner === myName)) &&
          (!filters.owner || i.owner === filters.owner) &&
          (!filters.status || i.status === filters.status) &&
          (!filters.phase || i.phase === filters.phase),
      ),
    [items, tab, filters, myName],
  )

  const owners = useMemo(
    () => [...new Set(items.map((i) => i.owner).filter(Boolean))],
    [items],
  )

  const startEdit = (item) => {
    setEditingId(item.id)
    setForm({ ...emptyForm, ...item, due_date: item.due_date || '' })
    setAdding(false)
  }

  const startAdd = () => {
    setAdding(true)
    setEditingId(null)
    setForm({ ...emptyForm, is_followup: tab === 'followup' })
  }

  const cancel = () => {
    setAdding(false)
    setEditingId(null)
    setForm(emptyForm)
  }

  const save = async () => {
    if (!form.title.trim()) return
    const payload = { ...form, due_date: form.due_date || null }
    if (adding) {
      await createItem(slug, 'tasks', payload)
    } else {
      await updateItem(slug, 'tasks', editingId, payload)
    }
    cancel()
    load()
  }

  const remove = async (id) => {
    if (!confirm('Delete this task?')) return
    await deleteItem(slug, 'tasks', id)
    load()
  }

  const clone = async (id) => {
    await cloneItem(slug, 'tasks', id)
    load()
  }

  const handleMyNameChange = (e) => {
    setMyName(e.target.value)
    localStorage.setItem(MY_NAME_KEY, e.target.value)
  }

  const set = (key) => (e) => {
    const value = key === 'is_followup' ? e.target.checked : e.target.value
    setForm((f) => ({ ...f, [key]: value }))
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Task List</h2>
        <div className="flex flex-wrap items-center gap-3">
          <ImportExportBar slug={slug} entity="tasks" onImported={load} />
          <button
            onClick={startAdd}
            className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
          >
            + Add Task
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 mb-4 border-b border-gray-200">
        <div className="flex gap-2 overflow-x-auto">
          <button
            onClick={() => setTab('all')}
            className={`px-4 py-2 text-sm font-medium border-b-2 ${
              tab === 'all' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500'
            }`}
          >
            All Tasks
          </button>
          <button
            onClick={() => setTab('followup')}
            className={`px-4 py-2 text-sm font-medium border-b-2 ${
              tab === 'followup' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500'
            }`}
          >
            Follow-up Tasks
          </button>
          <button
            onClick={() => setTab('mine')}
            className={`px-4 py-2 text-sm font-medium border-b-2 ${
              tab === 'mine' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500'
            }`}
          >
            My Tasks
          </button>
        </div>
        <div className="pb-2">
          <input
            value={myName}
            onChange={handleMyNameChange}
            placeholder="I am… (owner name)"
            className="text-sm border border-gray-300 rounded-md px-2 py-1"
          />
        </div>
      </div>

      <div className="flex flex-wrap gap-3 mb-4">
        <select
          value={filters.owner}
          onChange={(e) => setFilters((f) => ({ ...f, owner: e.target.value }))}
          className="text-sm border border-gray-300 rounded-md px-2 py-1.5"
        >
          <option value="">All Owners</option>
          {owners.map((o) => (
            <option key={o}>{o}</option>
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
      </div>

      <div className="bg-white border border-gray-200 rounded-lg overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-gray-600 text-left">
            <tr>
              <th className="px-3 py-2">Code</th>
              <th className="px-3 py-2">Title</th>
              <th className="px-3 py-2">Phase</th>
              <th className="px-3 py-2">Owner</th>
              <th className="px-3 py-2">Due Date</th>
              <th className="px-3 py-2">Priority</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Follow-up</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {adding && <EditRow form={form} set={set} onSave={save} onCancel={cancel} />}
            {loading ? (
              <tr>
                <td colSpan={9} className="px-3 py-4 text-center text-gray-400">
                  Loading…
                </td>
              </tr>
            ) : loadError ? (
              <tr>
                <td colSpan={9} className="px-3 py-4 text-center text-red-600">
                  {loadError}{' '}
                  <button onClick={load} className="underline font-medium">
                    Retry
                  </button>
                </td>
              </tr>
            ) : filtered.length === 0 && !adding ? (
              <tr>
                <td colSpan={9} className="px-3 py-4 text-center text-gray-400">
                  No tasks yet.
                </td>
              </tr>
            ) : (
              filtered.map((item) =>
                editingId === item.id ? (
                  <EditRow key={item.id} form={form} set={set} onSave={save} onCancel={cancel} />
                ) : (
                  <Fragment key={item.id}>
                  <tr className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-3 py-2">{item.task_code}</td>
                    <td className="px-3 py-2 font-medium text-gray-900">{item.title}</td>
                    <td className="px-3 py-2">{item.phase}</td>
                    <td className="px-3 py-2">{item.owner}</td>
                    <td className="px-3 py-2">{item.due_date}</td>
                    <td className="px-3 py-2">{item.priority}</td>
                    <td className="px-3 py-2">
                      <StatusBadge status={item.status} />
                    </td>
                    <td className="px-3 py-2">{item.is_followup ? 'Yes' : ''}</td>
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
                        onClick={() => setCommentsOpenId((cur) => (cur === item.id ? null : item.id))}
                        className="text-gray-500 hover:underline mr-3"
                      >
                        Comments
                      </button>
                      <button
                        onClick={() => remove(item.id)}
                        className="text-red-600 hover:underline"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                  {commentsOpenId === item.id && (
                    <tr className="border-t border-gray-100 bg-gray-50/50">
                      <td colSpan={9} className="px-4 py-3">
                        <CommentsPanel slug={slug} entityType="task" entityId={item.id} />
                      </td>
                    </tr>
                  )}
                  </Fragment>
                ),
              )
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function EditRow({ form, set, onSave, onCancel }) {
  return (
    <tr className="border-t border-gray-100 bg-indigo-50/40">
      <td className="px-2 py-1.5">
        <input
          value={form.task_code || ''}
          onChange={set('task_code')}
          className="w-20 border border-gray-300 rounded px-2 py-1 text-sm"
        />
      </td>
      <td className="px-2 py-1.5">
        <input
          value={form.title || ''}
          onChange={set('title')}
          placeholder="Title"
          className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
        />
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
        <input
          type="date"
          value={form.due_date || ''}
          onChange={set('due_date')}
          className="border border-gray-300 rounded px-2 py-1 text-sm"
        />
      </td>
      <td className="px-2 py-1.5">
        <select
          value={form.priority || ''}
          onChange={set('priority')}
          className="border border-gray-300 rounded px-2 py-1 text-sm"
        >
          {PRIORITIES.map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
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
      <td className="px-2 py-1.5 text-center">
        <input type="checkbox" checked={!!form.is_followup} onChange={set('is_followup')} />
      </td>
      <td className="px-2 py-1.5 text-right whitespace-nowrap">
        <button onClick={onSave} className="text-green-600 hover:underline mr-3">
          Save
        </button>
        <button onClick={onCancel} className="text-gray-500 hover:underline">
          Cancel
        </button>
      </td>
    </tr>
  )
}
