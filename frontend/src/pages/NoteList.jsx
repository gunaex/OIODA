import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { listNotes, deleteNote, promoteNoteToTask, promoteNoteToIssue } from '../api/client'

export default function NoteList() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const [notes, setNotes] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [busyId, setBusyId] = useState(null)

  const load = () => {
    setLoading(true)
    setLoadError(null)
    listNotes(slug)
      .then(setNotes)
      .catch(() => setLoadError('Could not load notes — the backend may be unreachable.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [slug])

  const promote = async (id) => {
    setBusyId(id)
    try {
      await promoteNoteToTask(slug, id)
      load()
    } finally {
      setBusyId(null)
    }
  }

  const promoteIssue = async (id) => {
    setBusyId(id)
    try {
      await promoteNoteToIssue(slug, id)
      load()
    } finally {
      setBusyId(null)
    }
  }

  const remove = async (id) => {
    if (!confirm('Delete this note?')) return
    await deleteNote(slug, id)
    load()
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Notes</h2>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg divide-y divide-gray-100">
        {loading ? (
          <p className="px-4 py-4 text-center text-gray-400 text-sm">Loading…</p>
        ) : loadError ? (
          <p className="px-4 py-4 text-center text-sm text-red-600">
            {loadError}{' '}
            <button onClick={load} className="underline font-medium">
              Retry
            </button>
          </p>
        ) : notes.length === 0 ? (
          <p className="px-4 py-4 text-center text-gray-400 text-sm">
            No notes yet — use the quick note bar in the bottom-right corner (or press "n").
          </p>
        ) : (
          notes.map((n) => (
            <div key={n.id} className="flex items-center justify-between gap-3 px-4 py-3">
              <div className="min-w-0">
                <p className="text-sm text-gray-900 truncate">{n.content}</p>
                <p className="text-xs text-gray-400">{new Date(n.created_at).toLocaleString()}</p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                {n.status === 'Open' ? (
                  <>
                    <button
                      onClick={() => promote(n.id)}
                      disabled={busyId === n.id}
                      className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
                    >
                      Promote to Task
                    </button>
                    <button
                      onClick={() => promoteIssue(n.id)}
                      disabled={busyId === n.id}
                      className="px-3 py-1.5 text-sm border border-indigo-200 text-indigo-600 rounded-md hover:bg-indigo-50 disabled:opacity-50"
                    >
                      Promote to Issue
                    </button>
                  </>
                ) : n.status === 'PromotedToTask' ? (
                  <button
                    onClick={() => navigate(`/${slug}/tasks`)}
                    className="text-sm text-indigo-600 hover:underline"
                  >
                    → Task #{n.linked_task_id}
                  </button>
                ) : n.status === 'PromotedToIssue' ? (
                  <button
                    onClick={() => navigate(`/${slug}/board`)}
                    className="text-sm text-indigo-600 hover:underline"
                  >
                    → Issue #{n.linked_issue_id}
                  </button>
                ) : (
                  <span className="text-sm text-gray-400">{n.status}</span>
                )}
                <button onClick={() => remove(n.id)} className="text-sm text-red-600 hover:underline">
                  Delete
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
