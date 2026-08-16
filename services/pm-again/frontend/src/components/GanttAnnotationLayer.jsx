import { useCallback, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { createGanttAnnotation, updateGanttAnnotation, deleteGanttAnnotation } from '../api/client'

const COLORS = { yellow: '#eab308', red: '#ef4444', blue: '#3b82f6' }
const colorHex = (c) => COLORS[c] || '#6366f1'

function parseDateOnly(str) {
  const [y, m, d] = str.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function formatDateOnly(date) {
  const yyyy = date.getFullYear()
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const dd = String(date.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

// Mirrors frappe-gantt's internal (unexported) date_utils.diff() — see
// node_modules/frappe-gantt/src/date_utils.js — so pin x-positions land on
// exactly the same pixel the library would draw its own "today" line at.
// Only 'day' and 'month' scales are needed: those are the only units our
// four fixed view modes (Day/Week/Month/Quarter) ever produce.
function diffInScale(dateA, dateB, scale) {
  const msPerDay = 86400000
  const days =
    (dateA - dateB + (dateB.getTimezoneOffset() - dateA.getTimezoneOffset()) * 60000) / msPerDay
  if (scale === 'day') return days
  let yearDiff = dateA.getFullYear() - dateB.getFullYear()
  let monthDiff = dateA.getMonth() - dateB.getMonth() + dateA.getDate() / 31
  let months = yearDiff * 12 + monthDiff
  if (dateA.getDate() < dateB.getDate()) months--
  return months
}

// Approximate inverse of diffInScale, for translating a click's pixel
// position back into a calendar date. Exact for 'day' scale (Day/Week
// views); for 'month' scale (Month/Quarter views) a column is a whole
// month wide on screen anyway, so day-level precision within it isn't
// visually meaningful — a 30-day-per-month approximation is imperceptible.
function addApprox(date, qty, scale) {
  const daysPerUnit = scale === 'month' ? 30 : 1
  const d = new Date(date)
  d.setDate(d.getDate() + Math.round(qty * daysPerUnit))
  return d
}

function pinPosition(gantt, annotation, items) {
  const d = parseDateOnly(annotation.gantt_date)
  const diff = diffInScale(d, gantt.gantt_start, gantt.config.unit)
  const x = (diff / gantt.config.step) * gantt.config.column_width
  const rowIndex =
    annotation.linked_gantt_item_id != null
      ? items.findIndex((it) => it.id === annotation.linked_gantt_item_id)
      : -1
  const rowHeight = gantt.options.bar_height + gantt.options.padding
  const y =
    rowIndex >= 0
      ? gantt.config.header_height + rowIndex * rowHeight + rowHeight / 2
      : gantt.config.header_height + 6
  return { x, y }
}

/** Overlays date-pinned annotations on top of a live frappe-gantt instance.
 * Portals into a dedicated layer div appended to the library's own
 * `$container` (never touched by its clear()/render() cycle — see
 * clear() in node_modules/frappe-gantt/src/index.js) so pins scroll and
 * re-scale with the chart instead of being repositioned by hand on every
 * scroll event. */
export default function GanttAnnotationLayer({
  slug,
  gantt,
  renderTick,
  items,
  annotations,
  onChange,
  presentMode,
  placing,
  onPlacingDone,
}) {
  const [portalNode, setPortalNode] = useState(null)
  const [pins, setPins] = useState([])
  const [hoverId, setHoverId] = useState(null)
  const [pinnedId, setPinnedId] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [editDraft, setEditDraft] = useState({ content: '', color: 'yellow' })
  const [draftPin, setDraftPin] = useState(null)
  const [draftContent, setDraftContent] = useState('')
  const [draftColor, setDraftColor] = useState('yellow')

  // Re-appends the pin layer to the end of $container (clear()/render() in
  // node_modules/frappe-gantt/src/index.js remove and recreate the header/
  // extras elements on every redraw and re-append them — since later DOM
  // siblings paint, and intercept clicks, on top of earlier ones, this
  // keeps pins on top instead of getting shadowed by the header) and
  // recomputes every pin's x/y off the gantt instance's *current*
  // gantt_start/config, not a cached value.
  const sync = useCallback(() => {
    if (!gantt || !gantt.$container) {
      setPortalNode(null)
      setPins([])
      return
    }
    let node = gantt.$container.querySelector(':scope > .gantt-annotation-pin-layer')
    if (!node) {
      node = document.createElement('div')
      node.className = 'gantt-annotation-pin-layer'
      node.style.position = 'absolute'
      node.style.top = '0'
      node.style.left = '0'
      node.style.pointerEvents = 'none'
    }
    gantt.$container.appendChild(node)
    setPortalNode(node)
    setPins(annotations.map((a) => ({ annotation: a, ...pinPosition(gantt, a, items) })))
  }, [gantt, annotations, items])

  useEffect(() => {
    sync()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sync, renderTick])

  // frappe-gantt's `infinite_padding` option (on by default, see
  // defaults.js) silently shifts gantt_start/gantt_end and re-renders
  // internally when the user scrolls near either edge — via its own raw
  // 'mousewheel' listener, entirely outside React, so `renderTick` never
  // bumps for it. Without resyncing on the container's native 'scroll'
  // event too, pins silently drift out of alignment with the chart the
  // first time a scroll gesture crosses that internal extend threshold.
  useEffect(() => {
    if (!gantt || !gantt.$container) return
    gantt.$container.addEventListener('scroll', sync)
    return () => gantt.$container.removeEventListener('scroll', sync)
  }, [gantt, sync])

  // Click-to-place: armed only while `placing` is true (toolbar "+ Add
  // Note" button). Converts the click's pixel position back into a date
  // using the same gantt_start/step/column_width the chart itself uses.
  useEffect(() => {
    if (!gantt || !placing) return
    const handleClick = (e) => {
      const rect = gantt.$container.getBoundingClientRect()
      const x = e.clientX - rect.left + gantt.$container.scrollLeft
      const qty = (x / gantt.config.column_width) * gantt.config.step
      const date = addApprox(gantt.gantt_start, qty, gantt.config.unit)
      setDraftContent('')
      setDraftColor('yellow')
      setDraftPin({ x, y: gantt.config.header_height + 6, date: formatDateOnly(date) })
    }
    gantt.$container.addEventListener('click', handleClick)
    gantt.$container.style.cursor = 'crosshair'
    return () => {
      gantt.$container.removeEventListener('click', handleClick)
      gantt.$container.style.cursor = ''
    }
  }, [gantt, placing])

  useEffect(() => {
    if (!placing) setDraftPin(null)
  }, [placing])

  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.key !== 'Escape') return
      setPinnedId(null)
      setEditingId(null)
      setDraftPin(null)
      onPlacingDone?.()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (!portalNode) return null

  const openId = pinnedId ?? hoverId
  const openPin = pins.find((p) => p.annotation.id === openId)

  const startEdit = (annotation) => {
    setPinnedId(annotation.id)
    setEditingId(annotation.id)
    setEditDraft({ content: annotation.content, color: annotation.color })
  }

  const saveEdit = async (id) => {
    await updateGanttAnnotation(slug, id, editDraft)
    setEditingId(null)
    onChange()
  }

  const removeAnnotation = async (id) => {
    if (!confirm('Delete this note?')) return
    setPinnedId(null)
    setEditingId(null)
    await deleteGanttAnnotation(slug, id)
    onChange()
  }

  const saveDraft = async () => {
    if (!draftContent.trim()) return
    await createGanttAnnotation(slug, {
      gantt_date: draftPin.date,
      content: draftContent.trim(),
      color: draftColor,
    })
    setDraftPin(null)
    onChange()
    onPlacingDone?.()
  }

  return createPortal(
    <>
      {pins.map(({ annotation, x, y }) => (
        <div
          key={annotation.id}
          className="gantt-annotation-pin"
          title={annotation.content}
          style={{
            position: 'absolute',
            left: x - 8,
            top: y - 8,
            width: 16,
            height: 16,
            borderRadius: '50%',
            border: '2px solid white',
            boxShadow: '0 1px 3px rgba(0,0,0,.45)',
            backgroundColor: colorHex(annotation.color),
            cursor: 'pointer',
            pointerEvents: 'auto',
          }}
          onMouseEnter={() => setHoverId(annotation.id)}
          onMouseLeave={() => setHoverId((h) => (h === annotation.id ? null : h))}
          onClick={(e) => {
            e.stopPropagation()
            setPinnedId((cur) => (cur === annotation.id ? null : annotation.id))
            setEditingId(null)
          }}
          onDoubleClick={(e) => {
            e.stopPropagation()
            if (!presentMode) startEdit(annotation)
          }}
        />
      ))}

      {openPin && (
        <div
          className="bg-white border border-gray-200 rounded-md shadow-lg text-sm"
          style={{
            position: 'absolute',
            left: openPin.x,
            top: openPin.y + 14,
            width: 220,
            pointerEvents: 'auto',
            zIndex: 10,
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {editingId === openPin.annotation.id ? (
            <div className="p-2 space-y-2">
              <textarea
                value={editDraft.content}
                onChange={(e) => setEditDraft((d) => ({ ...d, content: e.target.value }))}
                rows={3}
                className="w-full border border-gray-300 rounded px-2 py-1 text-xs"
              />
              <select
                value={editDraft.color}
                onChange={(e) => setEditDraft((d) => ({ ...d, color: e.target.value }))}
                className="w-full border border-gray-300 rounded px-1 py-1 text-xs"
              >
                <option value="yellow">Yellow</option>
                <option value="red">Red</option>
                <option value="blue">Blue</option>
              </select>
              <div className="flex justify-between gap-1">
                <button
                  onClick={() => saveEdit(openPin.annotation.id)}
                  className="px-2 py-1 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700"
                >
                  Save
                </button>
                <button
                  onClick={() => removeAnnotation(openPin.annotation.id)}
                  className="px-2 py-1 text-xs text-red-600 hover:underline"
                >
                  Delete
                </button>
                <button
                  onClick={() => setEditingId(null)}
                  className="px-2 py-1 text-xs text-gray-500 hover:underline"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="p-2">
              <p className="text-xs text-gray-400 mb-1">{openPin.annotation.gantt_date}</p>
              <p className="text-gray-800 break-words">{openPin.annotation.content}</p>
              {!presentMode && (
                <div className="flex gap-3 mt-2">
                  <button
                    onClick={() => startEdit(openPin.annotation)}
                    className="text-xs text-indigo-600 hover:underline"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => removeAnnotation(openPin.annotation.id)}
                    className="text-xs text-red-600 hover:underline"
                  >
                    Delete
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {draftPin && (
        <div
          className="bg-white border border-gray-200 rounded-md shadow-lg text-sm"
          style={{
            position: 'absolute',
            left: draftPin.x,
            top: draftPin.y + 14,
            width: 220,
            pointerEvents: 'auto',
            zIndex: 10,
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="p-2 space-y-2">
            <p className="text-xs text-gray-400">{draftPin.date}</p>
            <textarea
              autoFocus
              value={draftContent}
              onChange={(e) => setDraftContent(e.target.value)}
              placeholder="Note…"
              rows={3}
              className="w-full border border-gray-300 rounded px-2 py-1 text-xs"
            />
            <select
              value={draftColor}
              onChange={(e) => setDraftColor(e.target.value)}
              className="w-full border border-gray-300 rounded px-1 py-1 text-xs"
            >
              <option value="yellow">Yellow</option>
              <option value="red">Red</option>
              <option value="blue">Blue</option>
            </select>
            <div className="flex gap-1">
              <button
                onClick={saveDraft}
                className="px-2 py-1 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700"
              >
                Save
              </button>
              <button
                onClick={() => {
                  setDraftPin(null)
                  onPlacingDone?.()
                }}
                className="px-2 py-1 text-xs text-gray-500 hover:underline"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </>,
    portalNode,
  )
}
