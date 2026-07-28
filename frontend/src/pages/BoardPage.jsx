import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  listBoardItems,
  createBoardItem,
  updateBoardItem,
  deleteBoardItem,
  promoteBoardItem,
  boardExportUrl,
} from '../api/client'
import LinkedNotesPanel from '../components/LinkedNotesPanel.jsx'
import SetPlanDatesControl from '../components/SetPlanDatesControl.jsx'

const TABS = ['issue', 'incident', 'backlog']
const TAB_LABELS = { issue: 'Issue', incident: 'Incident', backlog: 'Backlog' }
const STATUS_OPTIONS = {
  issue: ['Open', 'InProgress', 'Resolved', 'Closed', 'Promoted'],
  incident: ['Open', 'InProgress', 'Resolved', 'Closed', 'Promoted'],
  backlog: ['Backlog', 'Planned', 'InProgress', 'Done', 'Promoted'],
}
const SEVERITIES = ['Low', 'Medium', 'High', 'Critical']
const PHASES = ['UR', 'DR', 'DN', 'PU', 'ST', 'UT', 'TR', 'IP', 'MA']
// Mirrors the backend's VALID_PROMOTIONS map — used only to decide which
// buttons to show; the backend re-validates regardless.
const VALID_PROMOTIONS = {
  backlog: ['issue'],
  issue: ['incident', 'task'],
  incident: ['task'],
}
const SEVERITY_STYLES = {
  Critical: 'bg-red-100 text-red-700',
  High: 'bg-orange-100 text-orange-700',
  Medium: 'bg-yellow-100 text-yellow-700',
  Low: 'bg-gray-100 text-gray-600',
}

const emptyForm = { title: '', description: '', severity: '', phase: '', owner: '' }

export default function BoardPage() {
  const { slug } = useParams()
  const [tab, setTab] = useState('issue')
  const [view, setView] = useState('kanban')
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [filters, setFilters] = useState({ severity: '', status: '', phase: '', owner: '' })
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [promotingItem, setPromotingItem] = useState(null)
  const [detailItem, setDetailItem] = useState(null)

  const load = () => {
    setLoading(true)
    setLoadError(null)
    listBoardItems(slug, tab, Object.fromEntries(Object.entries(filters).filter(([, v]) => v)))
      .then(setItems)
      .catch(() => setLoadError(`Could not load ${tab} items — the backend may be unreachable.`))
      .finally(() => setLoading(false))
  }

  useEffect(load, [slug, tab, filters])

  const owners = useMemo(() => [...new Set(items.map((i) => i.owner).filter(Boolean))], [items])

  const startAdd = () => {
    setAdding(true)
    setForm(emptyForm)
  }

  const save = async () => {
    if (!form.title.trim()) return
    await createBoardItem(slug, { ...form, item_type: tab })
    setAdding(false)
    setForm(emptyForm)
    load()
  }

  const changeStatus = async (item, status) => {
    await updateBoardItem(slug, item.id, { status })
    load()
  }

  const remove = async (id) => {
    if (!confirm('Delete this item?')) return
    await deleteBoardItem(slug, id)
    load()
  }

  const doPromote = async (targetType) => {
    await promoteBoardItem(slug, promotingItem.id, targetType)
    setPromotingItem(null)
    load()
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Issue / Incident / Backlog Board</h2>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex border border-gray-300 rounded-md overflow-hidden">
            {['kanban', 'list'].map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`px-3 py-1.5 text-sm capitalize ${
                  view === v ? 'bg-indigo-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'
                }`}
              >
                {v}
              </button>
            ))}
          </div>
          <a
            href={boardExportUrl(slug, tab)}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
          >
            Export
          </a>
          <button
            onClick={startAdd}
            className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
          >
            + Add {TAB_LABELS[tab]}
          </button>
        </div>
      </div>

      <div className="flex gap-2 mb-4 border-b border-gray-200">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 ${
              tab === t ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500'
            }`}
          >
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap gap-3 mb-4">
        <select
          value={filters.severity}
          onChange={(e) => setFilters((f) => ({ ...f, severity: e.target.value }))}
          className="text-sm border border-gray-300 rounded-md px-2 py-1.5"
        >
          <option value="">All Severities</option>
          {SEVERITIES.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <select
          value={filters.status}
          onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
          className="text-sm border border-gray-300 rounded-md px-2 py-1.5"
        >
          <option value="">All Statuses</option>
          {STATUS_OPTIONS[tab].map((s) => (
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
      </div>

      {adding && (
        <div className="mb-4 p-4 bg-white border border-gray-200 rounded-lg flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[180px]">
            <label className="block text-xs text-gray-500 mb-1">Title</label>
            <input
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Severity</label>
            <select
              value={form.severity}
              onChange={(e) => setForm((f) => ({ ...f, severity: e.target.value }))}
              className="border border-gray-300 rounded px-2 py-1 text-sm"
            >
              <option value="">-</option>
              {SEVERITIES.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Phase</label>
            <select
              value={form.phase}
              onChange={(e) => setForm((f) => ({ ...f, phase: e.target.value }))}
              className="border border-gray-300 rounded px-2 py-1 text-sm"
            >
              <option value="">-</option>
              {PHASES.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Owner</label>
            <input
              value={form.owner}
              onChange={(e) => setForm((f) => ({ ...f, owner: e.target.value }))}
              className="w-24 border border-gray-300 rounded px-2 py-1 text-sm"
            />
          </div>
          <div className="flex gap-2">
            <button onClick={save} className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700">
              Save
            </button>
            <button
              onClick={() => setAdding(false)}
              className="px-3 py-1.5 text-sm text-gray-600 border border-gray-200 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <p className="text-gray-400 text-sm">Loading…</p>
      ) : loadError ? (
        <p className="text-sm text-red-600">
          {loadError}{' '}
          <button onClick={load} className="underline font-medium">
            Retry
          </button>
        </p>
      ) : view === 'kanban' ? (
        <KanbanView
          items={items}
          statuses={STATUS_OPTIONS[tab]}
          onChangeStatus={changeStatus}
          onPromote={setPromotingItem}
          onDelete={remove}
          onOpenDetail={setDetailItem}
        />
      ) : (
        <ListView
          items={items}
          onChangeStatus={changeStatus}
          onPromote={setPromotingItem}
          onDelete={remove}
          onOpenDetail={setDetailItem}
        />
      )}

      {detailItem && (
        <BoardItemDetailModal slug={slug} item={detailItem} onClose={() => setDetailItem(null)} />
      )}

      {promotingItem && (
        <PromoteModal
          item={promotingItem}
          targets={VALID_PROMOTIONS[promotingItem.item_type] || []}
          onPromote={doPromote}
          onClose={() => setPromotingItem(null)}
        />
      )}
    </div>
  )
}

function Card({ item, onPromote, onDelete, onOpenDetail }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="text-xs text-gray-500">{item.item_code}</div>
        {item.severity && (
          <span className={`px-1.5 py-0.5 text-[10px] uppercase tracking-wide rounded ${SEVERITY_STYLES[item.severity]}`}>
            {item.severity}
          </span>
        )}
      </div>
      <div className="text-sm font-medium text-gray-900 mt-1">{item.title}</div>
      <div className="text-xs text-gray-500 mt-1">
        {item.owner || 'Unassigned'}
        {item.sla_due_date && <> · SLA {item.sla_due_date}</>}
      </div>
      {item.linked_task_id && (
        <div className="text-xs text-indigo-600 mt-1">→ Task #{item.linked_task_id}</div>
      )}
      <div className="flex items-center gap-3 mt-2">
        <button onClick={() => onOpenDetail(item)} className="text-xs text-gray-500 hover:underline">
          Details
        </button>
        {item.status !== 'Promoted' && (
          <button onClick={() => onPromote(item)} className="text-xs text-indigo-600 hover:underline">
            Promote →
          </button>
        )}
        <button onClick={() => onDelete(item.id)} className="text-xs text-red-600 hover:underline">
          Delete
        </button>
      </div>
    </div>
  )
}

function KanbanView({ items, statuses, onChangeStatus, onPromote, onDelete, onOpenDetail }) {
  return (
    <div className="flex gap-4 overflow-x-auto pb-2">
      {statuses.map((status) => {
        const columnItems = items.filter((i) => i.status === status)
        return (
          <div key={status} className="bg-gray-50 border border-gray-200 rounded-lg p-3 w-64 shrink-0">
            <div className="text-xs font-semibold text-gray-500 uppercase mb-3">
              {status} ({columnItems.length})
            </div>
            <div className="space-y-2">
              {columnItems.map((item) => (
                <div key={item.id}>
                  <Card item={item} onPromote={onPromote} onDelete={onDelete} onOpenDetail={onOpenDetail} />
                  {status !== 'Promoted' && (
                    <MoveSelect item={item} statuses={statuses} onChangeStatus={onChangeStatus} />
                  )}
                </div>
              ))}
              {columnItems.length === 0 && <p className="text-xs text-gray-400">No items.</p>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function MoveSelect({ item, statuses, onChangeStatus }) {
  return (
    <select
      value={item.status}
      onChange={(e) => onChangeStatus(item, e.target.value)}
      className="mt-1 w-full text-xs border border-gray-200 rounded px-1 py-0.5"
    >
      {statuses.map((s) => (
        <option key={s} value={s}>
          Move to {s}
        </option>
      ))}
    </select>
  )
}

function ListView({ items, onChangeStatus, onPromote, onDelete, onOpenDetail }) {
  if (items.length === 0) {
    return <p className="text-gray-400 text-sm">No items.</p>
  }
  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50 text-gray-600 text-left">
          <tr>
            <th className="px-3 py-2">Code</th>
            <th className="px-3 py-2">Title</th>
            <th className="px-3 py-2">Severity</th>
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2">Phase</th>
            <th className="px-3 py-2">Owner</th>
            <th className="px-3 py-2">SLA</th>
            <th className="px-3 py-2"></th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} className="border-t border-gray-100 hover:bg-gray-50">
              <td className="px-3 py-2">{item.item_code}</td>
              <td className="px-3 py-2 font-medium text-gray-900">{item.title}</td>
              <td className="px-3 py-2">
                {item.severity && (
                  <span className={`px-1.5 py-0.5 text-[10px] uppercase tracking-wide rounded ${SEVERITY_STYLES[item.severity]}`}>
                    {item.severity}
                  </span>
                )}
              </td>
              <td className="px-3 py-2">{item.status}</td>
              <td className="px-3 py-2">{item.phase}</td>
              <td className="px-3 py-2">{item.owner}</td>
              <td className="px-3 py-2">{item.sla_due_date}</td>
              <td className="px-3 py-2 text-right whitespace-nowrap">
                <button onClick={() => onOpenDetail(item)} className="text-gray-500 hover:underline mr-3">
                  Details
                </button>
                {item.status !== 'Promoted' && (
                  <button onClick={() => onPromote(item)} className="text-indigo-600 hover:underline mr-3">
                    Promote →
                  </button>
                )}
                <button onClick={() => onDelete(item.id)} className="text-red-600 hover:underline">
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// Board items have no dedicated detail route (they live on this board), so
// the "detail view" the Note System / Progress Matrix specs hang their
// panels off is this modal.
function BoardItemDetailModal({ slug, item, onClose }) {
  return (
    <div className="fixed inset-0 bg-black/30 flex items-start justify-center z-50 p-4 overflow-y-auto" onClick={onClose}>
      <div className="bg-white rounded-lg p-6 w-full max-w-2xl my-8" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <div className="text-xs text-gray-500">{item.item_code}</div>
            <h3 className="text-lg font-semibold text-gray-900">{item.title}</h3>
            <div className="text-sm text-gray-500 mt-1">
              {item.status}
              {item.severity && <> · {item.severity}</>}
              {item.phase && <> · {item.phase}</>} · Owner: {item.owner || '-'}
              {item.sla_due_date && <> · SLA {item.sla_due_date}</>}
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-sm">
            ✕
          </button>
        </div>
        {item.description && <p className="text-sm text-gray-700 mb-4 whitespace-pre-wrap">{item.description}</p>}

        <div className="space-y-4">
          {/* Board items have no Gantt bar, so this is the only place their
              Progress Matrix baseline can be set. entity_type is board_item
              here — the API's flavour aliases are for filtering, not writing. */}
          <SetPlanDatesControl slug={slug} entityType="board_item" entityId={item.id} />
          <LinkedNotesPanel slug={slug} entityType={item.item_type} entityId={item.id} title={item.title} />
        </div>
      </div>
    </div>
  )
}

function PromoteModal({ item, targets, onPromote, onClose }) {
  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-white rounded-lg p-6 w-full max-w-sm"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="font-semibold text-gray-900 mb-1">Promote "{item.title}"</h3>
        <p className="text-sm text-gray-500 mb-4">Choose where this item should go next.</p>
        <div className="flex flex-col gap-2">
          {targets.length === 0 && <p className="text-sm text-gray-400">No promotion path available.</p>}
          {targets.map((t) => (
            <button
              key={t}
              onClick={() => onPromote(t)}
              className="px-3 py-2 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 capitalize"
            >
              → {t}
            </button>
          ))}
          <button
            onClick={onClose}
            className="px-3 py-2 text-sm text-gray-600 border border-gray-200 rounded-md hover:bg-gray-50 mt-2"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
