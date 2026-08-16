import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { search, listProjects, createWhiteboard } from '../api/client'
import { useAuth } from '../auth/AuthContext.jsx'
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

// `internalOnly` mirrors the tabs Layout.jsx already hides for client_viewer —
// the backend 403s these anyway (require_internal), this just avoids offering
// an action that would fail.
const ACTIONS = [
  { id: 'new-task', label: 'New Task', internalOnly: true, requiresSlug: true },
  { id: 'new-note', label: 'New Note', internalOnly: true, requiresSlug: true },
  { id: 'new-whiteboard', label: 'New Whiteboard', internalOnly: true, requiresSlug: true },
  { id: 'goto-dashboard', label: 'Go to Dashboard', requiresSlug: true },
  { id: 'goto-documents', label: 'Go to Documents', requiresSlug: true },
  { id: 'goto-gantt', label: 'Go to Gantt', requiresSlug: true },
  { id: 'switch-project', label: 'Switch Project' },
]

export default function CommandPalette() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const isClientViewer = user?.role === 'client_viewer'
  const inputRef = useRef(null)

  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [projects, setProjects] = useState(null)
  const [projectMode, setProjectMode] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)

  const close = useCallback(() => {
    setOpen(false)
    setQuery('')
    setSearchResults([])
    setProjectMode(false)
    setActiveIndex(0)
  }, [])

  useGlobalHotkey(
    'k',
    useCallback(
      (e) => {
        e.preventDefault()
        setOpen((o) => !o)
      },
      [],
    ),
    { ctrlOrCmd: true, allowInFormTags: true },
  )

  useEffect(() => {
    if (open) {
      // Let the modal mount before focusing.
      const id = setTimeout(() => inputRef.current?.focus(), 0)
      return () => clearTimeout(id)
    }
  }, [open])

  const isCommandMode = query.startsWith('>')
  const commandQuery = isCommandMode ? query.slice(1).trim().toLowerCase() : ''

  // Plain-text search — same 200ms debounce as SearchBar. Skipped entirely
  // for client_viewer since the backend 403s the whole /search endpoint for
  // that role (router-level require_internal).
  useEffect(() => {
    if (isClientViewer || projectMode || isCommandMode || !slug || query.trim().length < 2) {
      setSearchResults([])
      return
    }
    const handle = setTimeout(() => {
      search(slug, query.trim()).then(setSearchResults)
    }, 200)
    return () => clearTimeout(handle)
  }, [query, slug, isCommandMode, projectMode, isClientViewer])

  useEffect(() => {
    if (projectMode && projects === null) {
      listProjects().then(setProjects)
    }
  }, [projectMode, projects])

  useEffect(() => {
    setActiveIndex(0)
  }, [query, projectMode, searchResults.length])

  if (!open) return null

  const availableActions = ACTIONS.filter(
    (a) => (!a.requiresSlug || slug) && (!a.internalOnly || !isClientViewer),
  )
  const filteredActions = commandQuery
    ? availableActions.filter((a) => a.label.toLowerCase().includes(commandQuery))
    : availableActions

  const filteredProjects = projectMode
    ? (projects || []).filter((p) => p.name.toLowerCase().includes(query.trim().toLowerCase()))
    : []

  const list = projectMode ? filteredProjects : isCommandMode ? filteredActions : searchResults

  const runAction = async (action) => {
    switch (action.id) {
      case 'new-task':
        close()
        navigate(`/${slug}/tasks`, { state: { autoAdd: true } })
        break
      case 'new-note':
        close()
        document.getElementById('quick-note-input')?.focus()
        break
      case 'new-whiteboard': {
        const board = await createWhiteboard(slug, { title: `Untitled ${new Date().toLocaleString()}` })
        close()
        navigate(`/${slug}/whiteboards/${board.id}`)
        break
      }
      case 'goto-dashboard':
        close()
        navigate(`/${slug}/dashboard`)
        break
      case 'goto-documents':
        close()
        navigate(`/${slug}/documents`)
        break
      case 'goto-gantt':
        close()
        navigate(`/${slug}/gantt`)
        break
      case 'switch-project':
        setProjectMode(true)
        setQuery('')
        break
      default:
        break
    }
  }

  const selectAt = (index) => {
    const item = list[index]
    if (!item) return
    if (projectMode) {
      close()
      navigate(`/${item.slug}/dashboard`)
    } else if (isCommandMode) {
      runAction(item)
    } else {
      close()
      if (item.type === 'document') {
        navigate(`/${slug}/documents/${item.id}`)
      } else {
        navigate(`/${slug}/${TYPE_ROUTES[item.type]}`)
      }
    }
  }

  const onKeyDown = (e) => {
    if (e.key === 'Escape') {
      e.preventDefault()
      if (projectMode) {
        setProjectMode(false)
        setQuery('')
      } else {
        close()
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex((i) => Math.min(i + 1, list.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      selectAt(activeIndex)
    }
  }

  const placeholder = projectMode
    ? 'Switch to project…'
    : isClientViewer
      ? 'Type > for actions…'
      : 'Search, or type > for actions…'

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 px-4 bg-black/30" onClick={close}>
      <div
        className="w-full max-w-lg bg-white rounded-lg shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-200">
          {projectMode && <span className="text-xs text-gray-400 shrink-0">Project:</span>}
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={placeholder}
            className="w-full text-sm outline-none py-1"
          />
        </div>

        {isClientViewer && !isCommandMode && !projectMode && (
          <p className="px-3 py-3 text-xs text-gray-400">
            Search is unavailable for your role — type <span className="font-mono">&gt;</span> for actions.
          </p>
        )}

        {list.length > 0 && (
          <ul className="max-h-80 overflow-y-auto">
            {list.map((item, i) => (
              <li key={projectMode ? item.slug : isCommandMode ? item.id : `${item.type}-${item.id}`}>
                <button
                  onClick={() => selectAt(i)}
                  onMouseEnter={() => setActiveIndex(i)}
                  className={`w-full text-left px-3 py-2 text-sm flex items-center gap-2 ${
                    i === activeIndex ? 'bg-indigo-50' : 'hover:bg-gray-50'
                  }`}
                >
                  {projectMode ? (
                    <span className="truncate">{item.name}</span>
                  ) : isCommandMode ? (
                    <>
                      <span className="px-1.5 py-0.5 text-[10px] uppercase tracking-wide rounded bg-indigo-100 text-indigo-600 shrink-0">
                        Action
                      </span>
                      <span className="truncate">{item.label}</span>
                    </>
                  ) : (
                    <>
                      <span className="px-1.5 py-0.5 text-[10px] uppercase tracking-wide rounded bg-gray-100 text-gray-500 shrink-0">
                        {TYPE_LABELS[item.type]}
                      </span>
                      <span className="truncate">{item.title}</span>
                      {item.subtitle && (
                        <span className="text-gray-400 text-xs shrink-0">{item.subtitle}</span>
                      )}
                    </>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}

        {isCommandMode && filteredActions.length === 0 && (
          <p className="px-3 py-3 text-xs text-gray-400">No matching actions.</p>
        )}
        {projectMode && filteredProjects.length === 0 && projects !== null && (
          <p className="px-3 py-3 text-xs text-gray-400">No matching projects.</p>
        )}

        <div className="px-3 py-1.5 text-[10px] text-gray-400 border-t border-gray-100 flex gap-3">
          <span>↑↓ navigate</span>
          <span>Enter select</span>
          <span>Esc close</span>
        </div>
      </div>
    </div>
  )
}
