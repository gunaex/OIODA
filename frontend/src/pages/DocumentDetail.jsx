import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  getDocument,
  listSignoffs,
  submitDocumentForReview,
  signoffDocument,
  uploadDocumentFile,
  updateItem,
  openOrCreateWhiteboard,
} from '../api/client'
import StatusBadge from '../components/StatusBadge.jsx'
import CommentsPanel from '../components/CommentsPanel.jsx'

const PHASES = ['UR', 'DR', 'DN', 'PU', 'ST', 'UT', 'TR', 'IP', 'MA']

export default function DocumentDetail() {
  const { slug, id } = useParams()
  const navigate = useNavigate()
  const [doc, setDoc] = useState(null)
  const [signoffs, setSignoffs] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [signoffForm, setSignoffForm] = useState({ signed_by: '', signed_role: '', comment: '' })
  const [editing, setEditing] = useState(false)
  const [editForm, setEditForm] = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    Promise.all([getDocument(slug, id), listSignoffs(slug, id)])
      .then(([d, s]) => {
        setDoc(d)
        setSignoffs(s)
      })
      .catch(() => setError('Could not load this document — the backend may be unreachable.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [slug, id])

  const runAction = async (fn) => {
    setBusy(true)
    setError(null)
    try {
      await fn()
      load()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Action failed')
    } finally {
      setBusy(false)
    }
  }

  const handleSubmitReview = () => runAction(() => submitDocumentForReview(slug, id))

  const startEdit = () => {
    setEditForm({
      doc_code: doc.doc_code || '',
      title: doc.title,
      phase: doc.phase || '',
      doc_type: doc.doc_type || '',
      owner: doc.owner || '',
    })
    setEditing(true)
  }

  const handleSaveEdit = () =>
    runAction(async () => {
      await updateItem(slug, 'documents', id, editForm)
      setEditing(false)
    })

  const handleSignoff = (status) =>
    runAction(() => {
      if (!signoffForm.signed_by.trim()) {
        throw { response: { data: { detail: 'Signed by is required' } } }
      }
      return signoffDocument(slug, id, { ...signoffForm, status }).then(() => {
        setSignoffForm({ signed_by: '', signed_role: '', comment: '' })
      })
    })

  const handleUpload = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    runAction(() => uploadDocumentFile(slug, id, file))
    e.target.value = ''
  }

  const openWhiteboard = async () => {
    const boardId = await openOrCreateWhiteboard(slug, 'document', Number(id), `Whiteboard: ${doc.title}`)
    navigate(`/${slug}/whiteboards/${boardId}`)
  }

  if (loading) {
    return <p className="text-gray-400 text-sm">Loading…</p>
  }

  if (!doc) {
    return (
      <p className="text-sm text-red-600">
        {error || 'Document not found.'}{' '}
        <button onClick={load} className="underline font-medium">
          Retry
        </button>
      </p>
    )
  }

  return (
    <div>
      <button
        onClick={() => navigate(`/${slug}/documents`)}
        className="text-sm text-gray-500 hover:text-gray-800 mb-4"
      >
        &larr; Documents
      </button>

      <div className="bg-white border border-gray-200 rounded-lg p-6 mb-4">
        {editing ? (
          <div className="flex flex-wrap items-end gap-3 mb-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Doc Code</label>
              <input
                value={editForm.doc_code}
                onChange={(e) => setEditForm((f) => ({ ...f, doc_code: e.target.value }))}
                className="w-28 border border-gray-300 rounded px-2 py-1 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Title</label>
              <input
                value={editForm.title}
                onChange={(e) => setEditForm((f) => ({ ...f, title: e.target.value }))}
                className="border border-gray-300 rounded px-2 py-1 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Phase</label>
              <select
                value={editForm.phase}
                onChange={(e) => setEditForm((f) => ({ ...f, phase: e.target.value }))}
                className="border border-gray-300 rounded px-2 py-1 text-sm"
              >
                <option value="">-</option>
                {PHASES.map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Doc Type</label>
              <input
                value={editForm.doc_type}
                onChange={(e) => setEditForm((f) => ({ ...f, doc_type: e.target.value }))}
                className="w-28 border border-gray-300 rounded px-2 py-1 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Owner</label>
              <input
                value={editForm.owner}
                onChange={(e) => setEditForm((f) => ({ ...f, owner: e.target.value }))}
                className="w-28 border border-gray-300 rounded px-2 py-1 text-sm"
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleSaveEdit}
                disabled={busy}
                className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
              >
                Save
              </button>
              <button
                onClick={() => setEditing(false)}
                className="px-3 py-1.5 text-sm text-gray-600 border border-gray-200 rounded-md hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
            <div>
              <div className="text-xs text-gray-500 mb-1">{doc.doc_code}</div>
              <h2 className="text-xl font-semibold text-gray-900">{doc.title}</h2>
              <div className="text-sm text-gray-500 mt-1">
                {doc.phase} · {doc.doc_type} · Owner: {doc.owner || '-'}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-500">v{doc.version}</span>
              <StatusBadge status={doc.status} />
              <button onClick={startEdit} className="text-sm text-indigo-600 hover:underline ml-2">
                Edit
              </button>
            </div>
          </div>
        )}

        {doc.status === 'Rejected' && (
          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2 mb-4">
            This document was rejected. Editing it (even without changes) moves it back to Draft so it can be
            resubmitted for review.
          </p>
        )}

        {error && <p className="text-sm text-red-600 mb-3">{error}</p>}

        <div className="flex flex-wrap items-center gap-3 mb-4">
          {doc.status === 'Draft' && (
            <button
              onClick={handleSubmitReview}
              disabled={busy}
              className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
            >
              Submit for Review
            </button>
          )}
          <label className="px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-50 cursor-pointer">
            Upload File
            <input type="file" className="hidden" onChange={handleUpload} />
          </label>
          <button
            onClick={openWhiteboard}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
          >
            Open/Create Whiteboard
          </button>
          {doc.file_path && (
            <span className="text-sm text-gray-500">Attached: {doc.file_path.split('/').pop()}</span>
          )}
        </div>

        {doc.status === 'InReview' && (
          <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
            <div className="text-sm font-medium text-gray-700 mb-3">Sign-off</div>
            <div className="flex flex-wrap gap-3 items-end mb-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Signed By</label>
                <input
                  value={signoffForm.signed_by}
                  onChange={(e) => setSignoffForm((f) => ({ ...f, signed_by: e.target.value }))}
                  className="border border-gray-300 rounded px-2 py-1 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Role</label>
                <input
                  value={signoffForm.signed_role}
                  onChange={(e) => setSignoffForm((f) => ({ ...f, signed_role: e.target.value }))}
                  placeholder="e.g. Client PM"
                  className="border border-gray-300 rounded px-2 py-1 text-sm"
                />
              </div>
              <div className="flex-1 min-w-[180px]">
                <label className="block text-xs text-gray-500 mb-1">Comment</label>
                <input
                  value={signoffForm.comment}
                  onChange={(e) => setSignoffForm((f) => ({ ...f, comment: e.target.value }))}
                  className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => handleSignoff('Approved')}
                disabled={busy}
                className="px-3 py-1.5 text-sm bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
              >
                Approve
              </button>
              <button
                onClick={() => handleSignoff('Rejected')}
                disabled={busy}
                className="px-3 py-1.5 text-sm bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50"
              >
                Reject
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Sign-off History</h3>
        {signoffs.length === 0 ? (
          <p className="text-sm text-gray-400">No sign-off records yet.</p>
        ) : (
          <ul className="space-y-3">
            {signoffs.map((s) => (
              <li key={s.id} className="flex items-start gap-3 text-sm">
                <span
                  className={`px-2 py-0.5 rounded-full text-xs shrink-0 ${
                    s.status === 'Approved' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                  }`}
                >
                  {s.status}
                </span>
                <div>
                  <div className="text-gray-900">
                    {s.signed_by} {s.signed_role ? `(${s.signed_role})` : ''}
                  </div>
                  <div className="text-gray-500 text-xs">{new Date(s.signed_at).toLocaleString()}</div>
                  {s.comment && <div className="text-gray-600 mt-1">{s.comment}</div>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="mt-4">
        <CommentsPanel slug={slug} entityType="document" entityId={Number(id)} />
      </div>
    </div>
  )
}
