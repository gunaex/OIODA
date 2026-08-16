import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  listWhiteboards,
  createWhiteboard,
  deleteWhiteboard,
  generateErdDiagram,
  generateDocumentWorkflowDiagram,
  generateBoardItemWorkflowDiagram,
} from '../api/client'

const ENTITY_LABELS = {
  project: 'Project',
  phase: 'Phase',
  function: 'Function',
  document: 'Document',
  task: 'Task',
}

export default function WhiteboardList() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const [boards, setBoards] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [creating, setCreating] = useState(false)
  const [title, setTitle] = useState('')
  const [generating, setGenerating] = useState(null)

  const load = () => {
    setLoading(true)
    setLoadError(null)
    listWhiteboards(slug)
      .then(setBoards)
      .catch(() => setLoadError('Could not load whiteboards — the backend may be unreachable.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [slug])

  const create = async (e) => {
    e.preventDefault()
    if (!title.trim()) return
    setCreating(true)
    try {
      const board = await createWhiteboard(slug, { title: title.trim() })
      navigate(`/${slug}/whiteboards/${board.id}`)
    } finally {
      setCreating(false)
    }
  }

  const remove = async (id, e) => {
    e.stopPropagation()
    if (!confirm('Delete this whiteboard?')) return
    await deleteWhiteboard(slug, id)
    load()
  }

  const generate = async (key, fn) => {
    setGenerating(key)
    try {
      const board = await fn(slug)
      navigate(`/${slug}/whiteboards/${board.id}`)
    } finally {
      setGenerating(null)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Whiteboards</h2>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        <button
          onClick={() => generate('erd', generateErdDiagram)}
          disabled={generating !== null}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
        >
          {generating === 'erd' ? 'Generating…' : 'Generate/Regenerate ERD'}
        </button>
        <button
          onClick={() => generate('doc-workflow', generateDocumentWorkflowDiagram)}
          disabled={generating !== null}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
        >
          {generating === 'doc-workflow' ? 'Generating…' : 'Generate Workflow: Document'}
        </button>
        <button
          onClick={() => generate('board-workflow', generateBoardItemWorkflowDiagram)}
          disabled={generating !== null}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
        >
          {generating === 'board-workflow' ? 'Generating…' : 'Generate Workflow: Board Item'}
        </button>
      </div>

      <form onSubmit={create} className="flex flex-col sm:flex-row gap-2 mb-6">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="New whiteboard title"
          className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <button
          type="submit"
          disabled={creating}
          className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 disabled:opacity-50"
        >
          {creating ? 'Creating…' : '+ New Whiteboard'}
        </button>
      </form>

      {loading ? (
        <p className="text-gray-400 text-sm">Loading…</p>
      ) : loadError ? (
        <p className="text-sm text-red-600">
          {loadError}{' '}
          <button onClick={load} className="underline font-medium">
            Retry
          </button>
        </p>
      ) : boards.length === 0 ? (
        <p className="text-gray-400 text-sm">No whiteboards yet. Create one above.</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {boards.map((b) => (
            <button
              key={b.id}
              onClick={() => navigate(`/${slug}/whiteboards/${b.id}`)}
              className="text-left p-4 bg-white border border-gray-200 rounded-lg hover:shadow-md hover:border-indigo-300 transition"
            >
              <div className="flex items-start justify-between gap-2">
                <h3 className="font-medium text-gray-900">{b.title}</h3>
                <span onClick={(e) => remove(b.id, e)} className="text-xs text-red-500 hover:underline shrink-0">
                  Delete
                </span>
              </div>
              {b.linked_entity_type && (
                <span className="inline-block mt-1 px-1.5 py-0.5 text-[10px] uppercase tracking-wide rounded bg-gray-100 text-gray-500">
                  {ENTITY_LABELS[b.linked_entity_type] || b.linked_entity_type} #{b.linked_entity_id}
                </span>
              )}
              <p className="text-xs text-gray-400 mt-2">
                Updated {new Date(b.updated_at).toLocaleString()}
              </p>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
