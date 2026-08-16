import { useCallback, useEffect, useMemo, useState } from 'react'
import { listNotePages, moveNoteTag } from '../api/client'

// Kanban-style board where the columns are hashtags. Dragging a card between
// columns doesn't just move a row — the backend rewrites `#oldtag` to
// `#newtag` inside the note's markdown and reindexes from there, so the note
// body stays the source of truth (spec §4.4).

const DEFAULT_COLUMN_COUNT = 10

export default function TagBoard({ slug, tags, canWrite, onOpenNote, onChanged }) {
  const [columns, setColumns] = useState([])
  const [notesByTag, setNotesByTag] = useState({})
  const [loading, setLoading] = useState(true)
  const [dragging, setDragging] = useState(null) // { noteId, fromTag }
  const [dropTarget, setDropTarget] = useState(null)
  const [error, setError] = useState(null)

  const topTags = useMemo(() => tags.slice(0, DEFAULT_COLUMN_COUNT).map((t) => t.tag), [tags])

  useEffect(() => {
    // Only seed the columns from the top tags once per project — after that
    // the user's own column picks stick even as counts shift.
    setColumns((current) => (current.length === 0 ? topTags : current))
  }, [topTags])

  const load = useCallback(() => {
    if (columns.length === 0) {
      setNotesByTag({})
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    Promise.all(columns.map((tag) => listNotePages(slug, { tag })))
      .then((results) => {
        setNotesByTag(Object.fromEntries(columns.map((tag, i) => [tag, results[i]])))
      })
      .catch(() => setError('Could not load the tag board.'))
      .finally(() => setLoading(false))
  }, [slug, columns])

  useEffect(load, [load])

  const drop = async (toTag) => {
    setDropTarget(null)
    const move = dragging
    setDragging(null)
    if (!move || move.fromTag === toTag) return
    try {
      await moveNoteTag(slug, move.noteId, move.fromTag, toTag)
      load()
      onChanged?.()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not move that note.')
    }
  }

  const addColumn = (tag) => {
    if (!tag || columns.includes(tag)) return
    setColumns((c) => [...c, tag])
  }

  const availableTags = tags.filter((t) => !columns.includes(t.tag))

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3 mb-3">
        <select
          value=""
          onChange={(e) => addColumn(e.target.value)}
          className="text-sm border border-gray-300 rounded-md px-2 py-1.5"
          disabled={availableTags.length === 0}
        >
          <option value="">+ Add tag column…</option>
          {availableTags.map((t) => (
            <option key={t.tag} value={t.tag}>
              #{t.tag} ({t.count})
            </option>
          ))}
        </select>
        {tags.length === 0 && <span className="text-sm text-gray-400">No tags yet — add #tags to a note first.</span>}
      </div>

      {error && <p className="text-sm text-red-600 mb-3">{error}</p>}

      {loading ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : columns.length === 0 ? (
        <p className="text-sm text-gray-400">Pick a tag column to get started.</p>
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-2">
          {columns.map((tag) => (
            <div
              key={tag}
              onDragOver={(e) => {
                if (!dragging) return
                e.preventDefault()
                setDropTarget(tag)
              }}
              onDragLeave={() => setDropTarget((t) => (t === tag ? null : t))}
              onDrop={(e) => {
                e.preventDefault()
                drop(tag)
              }}
              className={`border rounded-lg p-3 w-64 shrink-0 ${
                dropTarget === tag ? 'bg-indigo-50 border-indigo-300' : 'bg-gray-50 border-gray-200'
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold text-gray-500 uppercase">
                  #{tag} ({(notesByTag[tag] || []).length})
                </span>
                <button
                  onClick={() => setColumns((c) => c.filter((x) => x !== tag))}
                  title="Hide this column"
                  className="text-xs text-gray-400 hover:text-gray-600"
                >
                  ✕
                </button>
              </div>
              <div className="space-y-2">
                {(notesByTag[tag] || []).map((n) => (
                  <div
                    key={n.id}
                    draggable={canWrite}
                    onDragStart={() => setDragging({ noteId: n.id, fromTag: tag })}
                    onDragEnd={() => {
                      setDragging(null)
                      setDropTarget(null)
                    }}
                    className={`bg-white border border-gray-200 rounded-lg p-3 ${canWrite ? 'cursor-grab' : ''}`}
                  >
                    <button
                      onClick={() => onOpenNote(n.id)}
                      className="text-sm font-medium text-gray-900 text-left hover:underline"
                    >
                      {n.title}
                    </button>
                    {n.excerpt && <div className="text-xs text-gray-400 mt-1 line-clamp-2">{n.excerpt}</div>}
                    {n.tags.length > 1 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {n.tags
                          .filter((t) => t !== tag)
                          .map((t) => (
                            <span key={t} className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-500">
                              #{t}
                            </span>
                          ))}
                      </div>
                    )}
                  </div>
                ))}
                {(notesByTag[tag] || []).length === 0 && <p className="text-xs text-gray-400">No notes.</p>}
              </div>
            </div>
          ))}
        </div>
      )}
      {canWrite && columns.length > 1 && (
        <p className="text-xs text-gray-400 mt-3">
          Drag a card to another column to retag it — the note's markdown is rewritten, not just the index.
        </p>
      )}
    </div>
  )
}
