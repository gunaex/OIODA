import { useCallback, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { createNote } from '../api/client'
import useGlobalHotkey from '../hooks/useGlobalHotkey'

export default function QuickNoteBar() {
  const { slug } = useParams()
  const inputRef = useRef(null)
  const [content, setContent] = useState('')
  const [saving, setSaving] = useState(false)
  const [justSaved, setJustSaved] = useState(false)

  useGlobalHotkey(
    'n',
    useCallback((e) => {
      e.preventDefault()
      inputRef.current?.focus()
    }, []),
  )

  if (!slug) return null

  const submit = async (e) => {
    e.preventDefault()
    if (!content.trim() || saving) return
    setSaving(true)
    try {
      await createNote(slug, content.trim())
      setContent('')
      setJustSaved(true)
      setTimeout(() => setJustSaved(false), 1500)
    } finally {
      setSaving(false)
    }
  }

  return (
    <form
      onSubmit={submit}
      className="fixed bottom-4 right-4 z-40 flex items-center gap-2 bg-white border border-gray-200 rounded-full shadow-lg px-4 py-2 w-80 max-w-[calc(100vw-2rem)]"
    >
      <span className="text-gray-400 text-sm shrink-0">📝</span>
      <input
        id="quick-note-input"
        ref={inputRef}
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="Quick note… ( n ) + Enter"
        className="flex-1 min-w-0 text-sm outline-none"
      />
      {justSaved && <span className="text-xs text-green-600 shrink-0">Saved</span>}
    </form>
  )
}
