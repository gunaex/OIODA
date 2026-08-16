import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { listLinkedNotes, listNotePages, linkNoteToEntity } from '../api/client'
import { useAuth } from '../auth/AuthContext.jsx'

const MY_NAME_KEY = 'pm-again:my-name'

// "Which notes mention this thing?" — the entity side of the note system's
// backlinks, shown next to the existing Comments section on Task / Function /
// Document / Board Item.
//
// entityType is the singular name the API takes: task | function | document |
// issue | incident | backlog (the last three are board_item aliases).
export default function LinkedNotesPanel({ slug: slugProp, entityType, entityId, title }) {
  const params = useParams()
  const slug = slugProp || params.slug
  const navigate = useNavigate()
  const { user } = useAuth()
  const canWrite = user?.role !== 'client_viewer'

  const [notes, setNotes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [picking, setPicking] = useState(false)

  const load = () => {
    setLoading(true)
    setError(null)
    listLinkedNotes(slug, entityType, entityId)
      .then(setNotes)
      .catch(() => setError('Could not load linked notes.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [slug, entityType, entityId])

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6">
      <div className="flex items-center justify-between gap-3 mb-3">
        <h3 className="text-sm font-semibold text-gray-700">Linked Notes</h3>
        {canWrite && (
          <button onClick={() => setPicking(true)} className="text-sm text-indigo-600 hover:underline">
            Link to Note
          </button>
        )}
      </div>
      {loading ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : error ? (
        <p className="text-sm text-red-600">
          {error}{' '}
          <button onClick={load} className="underline font-medium">
            Retry
          </button>
        </p>
      ) : notes.length === 0 ? (
        <p className="text-sm text-gray-400">No notes link here yet.</p>
      ) : (
        <ul className="space-y-2">
          {notes.map((n) => (
            <li key={n.id}>
              <button
                onClick={() => navigate(`/${slug}/notes-hub?note=${n.id}`)}
                className="text-sm text-indigo-600 hover:underline"
              >
                {n.title}
              </button>
              {n.excerpt && <div className="text-xs text-gray-400 truncate">{n.excerpt}</div>}
              {n.tags.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {n.tags.map((t) => (
                    <span key={t} className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-600">
                      #{t}
                    </span>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {picking && (
        <LinkNoteModal
          slug={slug}
          entityType={entityType}
          entityId={entityId}
          defaultTitle={title}
          onClose={() => setPicking(false)}
          onLinked={() => {
            setPicking(false)
            load()
          }}
        />
      )}
    </div>
  )
}

function LinkNoteModal({ slug, entityType, entityId, defaultTitle, onClose, onLinked }) {
  const [candidates, setCandidates] = useState([])
  const [q, setQ] = useState('')
  const [newTitle, setNewTitle] = useState(defaultTitle ? `${defaultTitle} — notes` : '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    listNotePages(slug, { q: q || undefined })
      .then(setCandidates)
      .catch(() => setCandidates([]))
  }, [slug, q])

  // Either path just appends `[[entityType:CODE]]` to the note's markdown —
  // linking is a property of the note text, not a separate join table the
  // user has to keep in sync.
  const run = async (payload) => {
    setBusy(true)
    setError(null)
    try {
      await linkNoteToEntity(slug, entityType, entityId, {
        ...payload,
        created_by: localStorage.getItem(MY_NAME_KEY) || null,
      })
      onLinked()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not link that note.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-lg p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-semibold text-gray-900 mb-1">Link to Note</h3>
        <p className="text-sm text-gray-500 mb-4">
          Adds a <code className="text-xs">[[{entityType}:CODE]]</code> wiki-link to the note's markdown.
        </p>

        {error && <p className="text-sm text-red-600 mb-3">{error}</p>}

        <label className="block text-xs text-gray-500 mb-1">Find an existing note</label>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search notes…"
          className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm mb-2"
        />
        <ul className="max-h-48 overflow-y-auto border border-gray-100 rounded mb-4">
          {candidates.length === 0 ? (
            <li className="px-3 py-2 text-sm text-gray-400">No notes found.</li>
          ) : (
            candidates.map((n) => (
              <li key={n.id}>
                <button
                  disabled={busy}
                  onClick={() => run({ note_id: n.id })}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-indigo-50 disabled:opacity-50"
                >
                  {n.title}
                </button>
              </li>
            ))
          )}
        </ul>

        <label className="block text-xs text-gray-500 mb-1">…or create a new note</label>
        <div className="flex gap-2 mb-4">
          <input
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            placeholder="New note title"
            className="flex-1 border border-gray-300 rounded px-2 py-1.5 text-sm"
          />
          <button
            disabled={busy}
            onClick={() => run({ title: newTitle })}
            className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
          >
            Create
          </button>
        </div>

        <button
          onClick={onClose}
          className="w-full px-3 py-2 text-sm text-gray-600 border border-gray-200 rounded-md hover:bg-gray-50"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
