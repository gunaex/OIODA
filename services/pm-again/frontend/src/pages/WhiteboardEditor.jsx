import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { getWhiteboard, updateWhiteboard } from '../api/client'

// Public embed — no container of our own to run (see spec §1/§6: self-host
// is an upgrade path for later, swapped in by changing only this URL).
const DRAWIO_ORIGIN = 'https://embed.diagrams.net'
// saveAndExit=0: disables drawio's own "Save & Exit" flow, which is what
// nudges users toward its built-in Google Drive/OneDrive/GitHub storage
// integrations. We never enable those — every save goes through
// PUT /whiteboards/{id} below, drawio only ever sees XML we hand it.
const DRAWIO_SRC = `${DRAWIO_ORIGIN}/?embed=1&ui=min&spin=1&proto=json&saveAndExit=0`

export default function WhiteboardEditor() {
  const { slug, id } = useParams()
  const navigate = useNavigate()
  const iframeRef = useRef(null)
  const [board, setBoard] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [saveStatus, setSaveStatus] = useState('') // '' | 'saving' | 'saved' | 'error'
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleDraft, setTitleDraft] = useState('')

  const load = () => {
    setLoading(true)
    setLoadError(null)
    getWhiteboard(slug, id)
      .then(setBoard)
      .catch(() => setLoadError('Could not load this whiteboard — the backend may be unreachable.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [slug, id])

  const handleSave = useCallback(
    async (xml) => {
      setSaveStatus('saving')
      try {
        const updated = await updateWhiteboard(slug, id, { xml_content: xml })
        setBoard(updated)
        setSaveStatus('saved')
        setTimeout(() => setSaveStatus((s) => (s === 'saved' ? '' : s)), 1500)
      } catch {
        setSaveStatus('error')
      }
    },
    [slug, id],
  )

  // Wire up once `board` is loaded — the iframe only mounts once we have
  // xml_content to hand it, so by the time drawio fires "init" this
  // effect has already re-run with the loaded board in its closure.
  useEffect(() => {
    if (!board) return

    function onMessage(evt) {
      if (evt.origin !== DRAWIO_ORIGIN) return
      let msg
      try {
        msg = JSON.parse(evt.data)
      } catch {
        return
      }

      if (msg.event === 'init') {
        iframeRef.current?.contentWindow.postMessage(
          JSON.stringify({ action: 'load', xml: board.xml_content || '', autosave: 1 }),
          DRAWIO_ORIGIN,
        )
      } else if (msg.event === 'save' || msg.event === 'autosave') {
        if (typeof msg.xml === 'string') handleSave(msg.xml)
      }
    }

    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [board, handleSave])

  const startRenameTitle = () => {
    setTitleDraft(board.title)
    setEditingTitle(true)
  }

  const saveTitle = async () => {
    if (!titleDraft.trim()) return
    const updated = await updateWhiteboard(slug, id, { title: titleDraft.trim() })
    setBoard(updated)
    setEditingTitle(false)
  }

  if (loading) {
    return <p className="text-gray-400 text-sm">Loading…</p>
  }

  if (loadError || !board) {
    return (
      <p className="text-sm text-red-600">
        {loadError || 'Whiteboard not found.'}{' '}
        <button onClick={load} className="underline font-medium">
          Retry
        </button>
      </p>
    )
  }

  return (
    <div className="flex flex-col" style={{ height: 'calc(100vh - 140px)' }}>
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-3 min-w-0">
          <button onClick={() => navigate(`/${slug}/whiteboards`)} className="text-sm text-gray-500 hover:text-gray-800 shrink-0">
            &larr; Whiteboards
          </button>
          {editingTitle ? (
            <input
              autoFocus
              value={titleDraft}
              onChange={(e) => setTitleDraft(e.target.value)}
              onBlur={saveTitle}
              onKeyDown={(e) => e.key === 'Enter' && saveTitle()}
              className="text-lg font-semibold text-gray-900 border border-gray-300 rounded px-2 py-0.5"
            />
          ) : (
            <h2
              onClick={startRenameTitle}
              className="text-lg font-semibold text-gray-900 truncate cursor-text hover:bg-gray-50 px-1 rounded"
              title="Click to rename"
            >
              {board.title}
            </h2>
          )}
        </div>
        <div className="text-sm shrink-0">
          {saveStatus === 'saving' && <span className="text-gray-400">Saving…</span>}
          {saveStatus === 'saved' && <span className="text-green-600">Saved</span>}
          {saveStatus === 'error' && <span className="text-red-600">Save failed</span>}
        </div>
      </div>

      <div className="flex-1 border border-gray-200 rounded-lg overflow-hidden">
        <iframe
          ref={iframeRef}
          src={DRAWIO_SRC}
          title="Whiteboard"
          className="w-full h-full"
          style={{ border: 'none' }}
        />
      </div>
    </div>
  )
}
