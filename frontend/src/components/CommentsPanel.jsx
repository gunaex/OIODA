import { useEffect, useState } from 'react'
import { listComments, createComment, deleteComment } from '../api/client'

const MY_NAME_KEY = 'pm-again:my-name'

export default function CommentsPanel({ slug, entityType, entityId }) {
  const [comments, setComments] = useState([])
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)

  const load = () => {
    setLoading(true)
    setLoadError(null)
    listComments(slug, entityType, entityId)
      .then(setComments)
      .catch(() => setLoadError('Could not load comments.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [slug, entityType, entityId])

  const submit = async (e) => {
    e.preventDefault()
    if (!content.trim()) return
    const createdBy = localStorage.getItem(MY_NAME_KEY) || null
    await createComment(slug, entityType, entityId, content.trim(), createdBy)
    setContent('')
    load()
  }

  const remove = async (id) => {
    await deleteComment(slug, id)
    load()
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">Comments</h3>
      {loading ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : loadError ? (
        <p className="text-sm text-red-600 mb-3">
          {loadError}{' '}
          <button onClick={load} className="underline font-medium">
            Retry
          </button>
        </p>
      ) : comments.length === 0 ? (
        <p className="text-sm text-gray-400 mb-3">No comments yet.</p>
      ) : (
        <ul className="space-y-3 mb-4">
          {comments.map((c) => (
            <li key={c.id} className="text-sm border-b border-gray-100 pb-2 last:border-0">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <span className="font-medium text-gray-900">{c.created_by || 'Anonymous'}</span>{' '}
                  <span className="text-gray-400 text-xs">{new Date(c.created_at).toLocaleString()}</span>
                </div>
                <button onClick={() => remove(c.id)} className="text-xs text-red-500 hover:underline shrink-0">
                  Delete
                </button>
              </div>
              <div className="text-gray-700 mt-1">{c.content}</div>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={submit} className="flex gap-2">
        <input
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Add a comment…"
          className="flex-1 border border-gray-300 rounded px-2 py-1.5 text-sm"
        />
        <button type="submit" className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700">
          Post
        </button>
      </form>
    </div>
  )
}
