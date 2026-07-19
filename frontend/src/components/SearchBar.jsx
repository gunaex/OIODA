import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { search } from '../api/client'
import useGlobalHotkey from '../hooks/useGlobalHotkey'

const TYPE_LABELS = {
  function: 'Function',
  task: 'Task',
  document: 'Document',
  note: 'Note',
  issue: 'Issue',
  incident: 'Incident',
  backlog: 'Backlog',
}
const TYPE_ROUTES = {
  function: 'functions',
  task: 'tasks',
  document: 'documents',
  note: 'notes',
  issue: 'board',
  incident: 'board',
  backlog: 'board',
}

export default function SearchBar() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const inputRef = useRef(null)
  const [q, setQ] = useState('')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)

  useGlobalHotkey(
    '/',
    useCallback((e) => {
      e.preventDefault()
      inputRef.current?.focus()
    }, []),
  )

  useEffect(() => {
    if (!slug || q.trim().length < 2) {
      setResults([])
      return
    }
    const handle = setTimeout(() => {
      search(slug, q.trim()).then((r) => {
        setResults(r)
        setOpen(true)
      })
    }, 200)
    return () => clearTimeout(handle)
  }, [q, slug])

  const goTo = (result) => {
    setOpen(false)
    setQ('')
    if (result.type === 'document') {
      navigate(`/${slug}/documents/${result.id}`)
    } else {
      navigate(`/${slug}/${TYPE_ROUTES[result.type]}`)
    }
  }

  if (!slug) return null

  return (
    <div className="relative w-full max-w-xs">
      <input
        ref={inputRef}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => results.length > 0 && setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            setOpen(false)
            inputRef.current?.blur()
          }
        }}
        placeholder="Search… ( / )"
        className="w-full text-sm border border-gray-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500"
      />
      {open && results.length > 0 && (
        <ul className="absolute z-50 mt-1 w-full bg-white border border-gray-200 rounded-md shadow-lg max-h-72 overflow-y-auto">
          {results.map((r) => (
            <li key={`${r.type}-${r.id}`}>
              <button
                onClick={() => goTo(r)}
                className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 flex items-center gap-2"
              >
                <span className="px-1.5 py-0.5 text-[10px] uppercase tracking-wide rounded bg-gray-100 text-gray-500 shrink-0">
                  {TYPE_LABELS[r.type]}
                </span>
                <span className="truncate">{r.title}</span>
                {r.subtitle && <span className="text-gray-400 text-xs shrink-0">{r.subtitle}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
