import { useEffect, useMemo, useRef, useState } from 'react'
import MDEditor from '@uiw/react-md-editor'
import { activeTagFragment } from './noteMarkdownUtils.js'

// Markdown editor for note pages. The editing surface itself is the
// open-source @uiw/react-md-editor (split edit/preview) — the only thing
// added here is the quick-hashtag autocomplete, which the library has no
// concept of. That's a custom overlay positioned over the textarea rather
// than a fork of the library's toolbar.

const MAX_SUGGESTIONS = 8

export default function NoteEditor({ value, onChange, tags = [], height = 460 }) {
  const wrapperRef = useRef(null)
  const [fragment, setFragment] = useState(null)
  const [highlight, setHighlight] = useState(0)

  const suggestions = useMemo(() => {
    if (!fragment) return []
    return tags
      .filter((t) => t.tag.startsWith(fragment.query) && t.tag !== fragment.query)
      .slice(0, MAX_SUGGESTIONS)
  }, [fragment, tags])

  const textarea = () => wrapperRef.current?.querySelector('textarea')

  const refresh = () => {
    const el = textarea()
    if (!el) return
    setFragment(activeTagFragment(el.value, el.selectionStart))
    setHighlight(0)
  }

  const accept = (tag) => {
    const el = textarea()
    if (!el || !fragment) return
    const before = el.value.slice(0, fragment.start)
    const after = el.value.slice(el.selectionStart)
    const next = `${before}#${tag} ${after}`
    onChange(next)
    setFragment(null)
    // Restore the caret after React re-renders with the new value.
    const caret = before.length + tag.length + 2
    requestAnimationFrame(() => {
      const t = textarea()
      if (t) {
        t.focus()
        t.setSelectionRange(caret, caret)
      }
    })
  }

  // Keydown is bound on the wrapper in the capture phase so the dropdown can
  // claim Enter/arrows before the textarea inserts a newline.
  const onKeyDown = (e) => {
    if (!fragment || suggestions.length === 0) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlight((h) => (h + 1) % suggestions.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlight((h) => (h - 1 + suggestions.length) % suggestions.length)
    } else if (e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault()
      accept(suggestions[highlight].tag)
    } else if (e.key === 'Escape') {
      e.preventDefault()
      setFragment(null)
    }
  }

  useEffect(() => {
    const el = textarea()
    if (!el) return undefined
    el.addEventListener('click', refresh)
    el.addEventListener('keyup', refresh)
    el.addEventListener('blur', () => setTimeout(() => setFragment(null), 150))
    return () => {
      el.removeEventListener('click', refresh)
      el.removeEventListener('keyup', refresh)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div ref={wrapperRef} onKeyDownCapture={onKeyDown} className="relative" data-color-mode="light">
      <MDEditor
        value={value}
        onChange={(v) => onChange(v ?? '')}
        height={height}
        preview="edit"
        textareaProps={{ placeholder: 'Write markdown… use #tag and [[Note Title]] / [[task:CODE]]' }}
      />
      {fragment && suggestions.length > 0 && (
        <ul className="absolute left-3 bottom-3 z-20 w-56 bg-white border border-gray-200 rounded-md shadow-lg py-1 text-sm">
          <li className="px-3 py-1 text-[10px] uppercase tracking-wide text-gray-400">Tags in use</li>
          {suggestions.map((t, i) => (
            <li key={t.tag}>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => accept(t.tag)}
                onMouseEnter={() => setHighlight(i)}
                className={`w-full text-left px-3 py-1 flex justify-between gap-2 ${
                  i === highlight ? 'bg-indigo-50 text-indigo-700' : 'text-gray-700 hover:bg-gray-50'
                }`}
              >
                <span>#{t.tag}</span>
                <span className="text-xs text-gray-400">{t.count}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
