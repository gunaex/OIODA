import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import Gantt from 'frappe-gantt'
import '../vendor/frappe-gantt.css'
import { listItems, createItem, updateItem, deleteItem } from '../api/client'
import ImportExportBar from '../components/ImportExportBar.jsx'

// frappe-gantt has no built-in "Quarter" scale (only Hour/Quarter Day/Half
// Day/Day/Week/Month/Year) — define one so the fixed Day/Week/Month/Quarter
// button set in the fix spec has somewhere to point.
const QUARTER_VIEW_MODE = {
  name: 'Quarter',
  padding: '3m',
  step: '3m',
  column_width: 130,
  date_format: 'YYYY-MM',
  lower_text: (d) => `Q${Math.floor(d.getMonth() / 3) + 1}`,
  upper_text: (d, ld) => (!ld || d.getFullYear() !== ld.getFullYear() ? String(d.getFullYear()) : ''),
  thick_line: (d) => d.getMonth() % 3 === 0,
  snap_at: '1m',
}

// Fixed zoom levels only — no freeform/continuous zoom, so there's never an
// intermediate scale that forces a redraw mid-gesture.
const VIEW_MODES = ['Day', 'Week', 'Month', QUARTER_VIEW_MODE]
const VIEW_MODE_LABELS = ['Day', 'Week', 'Month', 'Quarter']

// Row sizing — explicit (not frappe-gantt's defaults left implicit) so the
// container-height formula below is guaranteed to match what actually gets
// drawn. With a fixed (non-'auto') container_height, frappe-gantt always
// reserves this much vertical space — short lists still fill it with empty
// grid rows instead of leaving blank page beneath a shrink-wrapped chart —
// and once real rows exceed it, `.gantt-container`'s own `overflow:auto`
// kicks in and scrolls internally instead of growing the page.
const BAR_HEIGHT = 30
const ROW_PADDING = 18
const UPPER_HEADER_HEIGHT = 45
const LOWER_HEADER_HEIGHT = 30
const HEADER_HEIGHT = UPPER_HEADER_HEIGHT + LOWER_HEADER_HEIGHT + 10
const VISIBLE_ROWS = 8 // within the requested 5–10 row range
const GANTT_CONTAINER_HEIGHT =
  HEADER_HEIGHT + ROW_PADDING + (BAR_HEIGHT + ROW_PADDING) * VISIBLE_ROWS - 10

const PHASES = ['UR', 'DR', 'DN', 'PU', 'ST', 'UT', 'TR', 'IP', 'MA']

const emptyForm = {
  name: '',
  phase: '',
  start_date: '',
  end_date: '',
  progress: 0,
  dependencies: '',
  is_milestone: false,
}

export default function GanttView() {
  const { slug } = useParams()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [viewMode, setViewMode] = useState('Day')
  const [editingId, setEditingId] = useState(null)
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const containerRef = useRef(null)
  const ganttRef = useRef(null)

  // Always-current handlers for the Gantt instance's callbacks. The Gantt
  // instance itself is only ever constructed once (see the effect below),
  // so its `on_date_change`/`on_progress_change`/`on_click` options are
  // fixed at construction time; they delegate through this ref so they
  // never see stale `slug`/`items` closures without forcing a rebuild.
  const handlersRef = useRef({})

  const load = () => {
    setLoading(true)
    setLoadError(null)
    listItems(slug, 'gantt')
      .then(setItems)
      .catch(() => setLoadError('Could not load the Gantt chart — the backend may be unreachable.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [slug])

  const tasks = useMemo(
    () =>
      items.map((item) => ({
        id: String(item.id),
        name: item.name,
        start: item.start_date,
        end: item.end_date,
        progress: item.progress || 0,
        dependencies: item.dependencies || '',
        custom_class: item.is_milestone ? 'milestone-bar' : '',
      })),
    [items],
  )

  handlersRef.current = {
    onDateChange: async (task, start, end) => {
      // frappe-gantt only fires this once, on drop — not per drag pixel —
      // so this already runs at most once per gesture.
      const start_date = formatDate(start)
      const end_date = formatDate(end)
      setItems((prev) =>
        prev.map((i) => (i.id === Number(task.id) ? { ...i, start_date, end_date } : i)),
      )
      await updateItem(slug, 'gantt', Number(task.id), { start_date, end_date })
    },
    onProgressChange: async (task, progress) => {
      setItems((prev) => prev.map((i) => (i.id === Number(task.id) ? { ...i, progress } : i)))
      await updateItem(slug, 'gantt', Number(task.id), { progress })
    },
    onClick: (task) => {
      const item = items.find((i) => String(i.id) === task.id)
      if (item) startEdit(item)
    },
  }

  // Create the Gantt instance exactly once, then feed it data updates via
  // its own `refresh()` API. The previous version wiped the container and
  // called `new Gantt(...)` on every data change (including after every
  // drag-drop), tearing down and rebuilding the whole SVG each time — that
  // full teardown/rebuild was the flicker. `refresh()` updates in place.
  useEffect(() => {
    if (!containerRef.current) return

    if (tasks.length === 0) {
      containerRef.current.innerHTML = ''
      ganttRef.current = null
      return
    }

    if (!ganttRef.current) {
      ganttRef.current = new Gantt(containerRef.current, tasks, {
        view_mode: viewMode,
        view_modes: VIEW_MODES,
        view_mode_select: false,
        bar_height: BAR_HEIGHT,
        padding: ROW_PADDING,
        upper_header_height: UPPER_HEADER_HEIGHT,
        lower_header_height: LOWER_HEADER_HEIGHT,
        container_height: GANTT_CONTAINER_HEIGHT,
        on_date_change: (task, start, end) => handlersRef.current.onDateChange(task, start, end),
        on_progress_change: (task, progress) => handlersRef.current.onProgressChange(task, progress),
        on_click: (task) => handlersRef.current.onClick(task),
      })
    } else {
      ganttRef.current.refresh(tasks)
    }
  }, [tasks])

  // Switch the existing instance's scale in place — `change_view_mode()`
  // redraws the grid without destroying/recreating the instance, so
  // flipping between Day/Week/Month/Quarter doesn't flash.
  useEffect(() => {
    ganttRef.current?.change_view_mode(viewMode)
  }, [viewMode])

  useEffect(() => {
    return () => {
      ganttRef.current = null
    }
  }, [])

  const startEdit = (item) => {
    setEditingId(item.id)
    setAdding(false)
    setForm({ ...emptyForm, ...item })
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
    if (!form.name.trim() || !form.start_date || !form.end_date) return
    if (adding) {
      await createItem(slug, 'gantt', form)
    } else {
      await updateItem(slug, 'gantt', editingId, form)
    }
    cancel()
    load()
  }

  const remove = async (id) => {
    if (!confirm('Delete this Gantt item?')) return
    await deleteItem(slug, 'gantt', id)
    cancel()
    load()
  }

  const set = (key) => (e) => {
    const value =
      key === 'is_milestone'
        ? e.target.checked
        : key === 'progress'
          ? Number(e.target.value)
          : e.target.value
    setForm((f) => ({ ...f, [key]: value }))
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Gantt Chart</h2>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex border border-gray-300 rounded-md overflow-hidden">
            {VIEW_MODE_LABELS.map((label) => (
              <button
                key={label}
                onClick={() => setViewMode(label)}
                className={`px-3 py-1.5 text-sm ${
                  viewMode === label
                    ? 'bg-indigo-600 text-white'
                    : 'bg-white text-gray-600 hover:bg-gray-50'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <ImportExportBar slug={slug} entity="gantt" onImported={load} />
          <button
            onClick={startAdd}
            className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
          >
            + Add Item
          </button>
        </div>
      </div>

      {(adding || editingId) && (
        <div className="mb-4 p-4 bg-white border border-gray-200 rounded-lg flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Name</label>
            <input
              value={form.name}
              onChange={set('name')}
              className="border border-gray-300 rounded px-2 py-1 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Phase</label>
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
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Start</label>
            <input
              type="date"
              value={form.start_date}
              onChange={set('start_date')}
              className="border border-gray-300 rounded px-2 py-1 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">End</label>
            <input
              type="date"
              value={form.end_date}
              onChange={set('end_date')}
              className="border border-gray-300 rounded px-2 py-1 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Progress %</label>
            <input
              type="number"
              min={0}
              max={100}
              value={form.progress}
              onChange={set('progress')}
              className="w-20 border border-gray-300 rounded px-2 py-1 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Depends on (ids)</label>
            <input
              value={form.dependencies || ''}
              onChange={set('dependencies')}
              placeholder="1,2"
              className="w-24 border border-gray-300 rounded px-2 py-1 text-sm"
            />
          </div>
          <label className="flex items-center gap-1 text-sm text-gray-700 pb-1.5">
            <input type="checkbox" checked={!!form.is_milestone} onChange={set('is_milestone')} />
            Milestone
          </label>
          <div className="flex gap-2 pb-0.5">
            <button
              onClick={save}
              className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
            >
              Save
            </button>
            {editingId && (
              <button
                onClick={() => remove(editingId)}
                className="px-3 py-1.5 text-sm text-red-600 border border-red-200 rounded-md hover:bg-red-50"
              >
                Delete
              </button>
            )}
            <button
              onClick={cancel}
              className="px-3 py-1.5 text-sm text-gray-600 border border-gray-200 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="bg-white border border-gray-200 rounded-lg p-4">
        {loading ? <p className="text-gray-400 text-sm">Loading…</p> : null}
        {!loading && loadError ? (
          <p className="text-sm text-red-600">
            {loadError}{' '}
            <button onClick={load} className="underline font-medium">
              Retry
            </button>
          </p>
        ) : null}
        {!loading && !loadError && items.length === 0 ? (
          <p className="text-gray-400 text-sm">No Gantt items yet. Add one above.</p>
        ) : null}
        {/* Kept permanently mounted (just hidden) so `containerRef`/`ganttRef`
            never go stale from React unmounting the node out from under them.
            frappe-gantt's own `.gantt-container` (built with a fixed,
            non-'auto' container_height above) handles both scroll axes
            itself — no need for an outer overflow wrapper. */}
        <div ref={containerRef} className={loading || items.length === 0 ? 'hidden' : ''} />
      </div>
    </div>
  )
}

function formatDate(d) {
  const date = d instanceof Date ? d : new Date(d)
  const yyyy = date.getFullYear()
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const dd = String(date.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}
