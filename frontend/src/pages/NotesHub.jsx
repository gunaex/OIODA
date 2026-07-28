import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import {
  listNotePages,
  getNotePage,
  createNotePage,
  updateNotePage,
  deleteNotePage,
  listNoteBacklinks,
  listTags,
} from '../api/client'
import { useAuth } from '../auth/AuthContext.jsx'
import NoteEditor from '../components/NoteEditor.jsx'
import NoteMarkdown from '../components/NoteMarkdown.jsx'
import TagBoard from '../components/TagBoard.jsx'
import { entityRoute } from '../components/noteNav.js'

const MY_NAME_KEY = 'pm-again:my-name'

export default function NotesHub() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { user } = useAuth()
  const canWrite = user?.role !== 'client_viewer'

  const [view, setView] = useState('pages') // pages | board
  const [notes, setNotes] = useState([])
  const [tags, setTags] = useState([])
  const [search, setSearch] = useState('')
  const [tagFilter, setTagFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)

  const selectedId = searchParams.get('note')
  const [note, setNote] = useState(null)
  const [draft, setDraft] = useState({ title: '', content_markdown: '' })
  const [dirty, setDirty] = useState(false)
  const [mode, setMode] = useState('preview') // preview | edit
  const [backlinks, setBacklinks] = useState([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const selectNote = (id) => setSearchParams(id ? { note: String(id) } : {}, { replace: false })

  const loadList = useCallback(() => {
    setLoading(true)
    setLoadError(null)
    Promise.all([listNotePages(slug, { tag: tagFilter || undefined, q: search || undefined }), listTags(slug)])
      .then(([n, t]) => {
        setNotes(n)
        setTags(t)
      })
      .catch(() => setLoadError('Could not load notes — the backend may be unreachable.'))
      .finally(() => setLoading(false))
  }, [slug, tagFilter, search])

  useEffect(loadList, [loadList])

  useEffect(() => {
    if (!selectedId) {
      setNote(null)
      setBacklinks([])
      return
    }
    setError(null)
    Promise.all([getNotePage(slug, selectedId), listNoteBacklinks(slug, selectedId)])
      .then(([n, b]) => {
        setNote(n)
        setDraft({ title: n.title, content_markdown: n.content_markdown || '' })
        setDirty(false)
        setBacklinks(b)
      })
      .catch(() => setError('Could not open this note.'))
  }, [slug, selectedId])

  const createNew = async () => {
    const created = await createNotePage(slug, {
      title: 'Untitled note',
      content_markdown: '',
      created_by: localStorage.getItem(MY_NAME_KEY) || null,
    })
    loadList()
    selectNote(created.id)
    setMode('edit')
  }

  const save = async () => {
    if (!draft.title.trim()) {
      setError('Title cannot be empty.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      // The save is what triggers the backend's hashtag/wiki-link resync, so
      // the tag list and backlinks are re-read straight after.
      const updated = await updateNotePage(slug, note.id, draft)
      setNote(updated)
      setDirty(false)
      loadList()
      listNoteBacklinks(slug, note.id).then(setBacklinks)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not save this note.')
    } finally {
      setSaving(false)
    }
  }

  const remove = async () => {
    if (!confirm(`Delete "${note.title}"?`)) return
    await deleteNotePage(slug, note.id)
    selectNote(null)
    loadList()
  }

  const onTagClick = (tag) => {
    setTagFilter(tag)
    setView('pages')
  }

  const onEntityClick = (kind, id) => {
    if (kind === 'note') {
      selectNote(id)
      return
    }
    navigate(entityRoute(slug, kind, id))
  }

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Notes</h2>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex border border-gray-300 rounded-md overflow-hidden">
            {[
              ['pages', 'Pages'],
              ['board', 'Tag Board'],
            ].map(([key, label]) => (
              <button
                key={key}
                onClick={() => setView(key)}
                className={`px-3 py-1.5 text-sm ${
                  view === key ? 'bg-indigo-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          {canWrite && (
            <button
              onClick={createNew}
              className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
            >
              + New Note
            </button>
          )}
        </div>
      </div>

      {loadError && (
        <p className="text-sm text-red-600 mb-3">
          {loadError}{' '}
          <button onClick={loadList} className="underline font-medium">
            Retry
          </button>
        </p>
      )}

      {view === 'board' ? (
        <TagBoard
          slug={slug}
          tags={tags}
          canWrite={canWrite}
          onOpenNote={(id) => {
            setView('pages')
            selectNote(id)
          }}
          onChanged={loadList}
        />
      ) : (
        <div className="flex flex-col md:flex-row gap-4">
          {/* Sidebar — the "file list" */}
          <aside className="md:w-72 shrink-0 bg-white border border-gray-200 rounded-lg p-3">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search notes…"
              className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm mb-2"
            />
            <select
              value={tagFilter}
              onChange={(e) => setTagFilter(e.target.value)}
              className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm mb-3"
            >
              <option value="">All tags</option>
              {tags.map((t) => (
                <option key={t.tag} value={t.tag}>
                  #{t.tag} ({t.count})
                </option>
              ))}
            </select>
            {loading ? (
              <p className="text-sm text-gray-400">Loading…</p>
            ) : notes.length === 0 ? (
              <p className="text-sm text-gray-400">No notes{tagFilter ? ` tagged #${tagFilter}` : ''} yet.</p>
            ) : (
              <ul className="space-y-1 max-h-[32rem] overflow-y-auto">
                {notes.map((n) => (
                  <li key={n.id}>
                    <button
                      onClick={() => selectNote(n.id)}
                      className={`w-full text-left px-2 py-1.5 rounded ${
                        String(n.id) === selectedId ? 'bg-indigo-50 text-indigo-800' : 'hover:bg-gray-50'
                      }`}
                    >
                      <div className="text-sm font-medium text-gray-900 truncate">{n.title}</div>
                      {n.excerpt && <div className="text-xs text-gray-400 truncate">{n.excerpt}</div>}
                      {n.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {n.tags.slice(0, 4).map((t) => (
                            <span key={t} className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-600">
                              #{t}
                            </span>
                          ))}
                        </div>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </aside>

          {/* Editor / preview */}
          <section className="flex-1 min-w-0">
            {!note ? (
              <div className="bg-white border border-gray-200 rounded-lg p-6 text-sm text-gray-400">
                Select a note on the left{canWrite ? ', or create a new one' : ''}.
              </div>
            ) : (
              <>
                <div className="bg-white border border-gray-200 rounded-lg p-4 mb-4">
                  <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
                    {canWrite ? (
                      <input
                        value={draft.title}
                        onChange={(e) => {
                          setDraft((d) => ({ ...d, title: e.target.value }))
                          setDirty(true)
                        }}
                        className="flex-1 min-w-[200px] text-lg font-semibold text-gray-900 border-b border-transparent focus:border-gray-300 outline-none"
                      />
                    ) : (
                      <h3 className="flex-1 text-lg font-semibold text-gray-900">{note.title}</h3>
                    )}
                    <div className="flex items-center gap-2">
                      {canWrite && (
                        <div className="flex border border-gray-300 rounded-md overflow-hidden">
                          {[
                            ['preview', 'Preview'],
                            ['edit', 'Edit'],
                          ].map(([key, label]) => (
                            <button
                              key={key}
                              onClick={() => setMode(key)}
                              className={`px-3 py-1 text-sm ${
                                mode === key ? 'bg-gray-800 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'
                              }`}
                            >
                              {label}
                            </button>
                          ))}
                        </div>
                      )}
                      {canWrite && (
                        <>
                          <button
                            onClick={save}
                            disabled={saving || !dirty}
                            className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
                          >
                            {saving ? 'Saving…' : dirty ? 'Save' : 'Saved'}
                          </button>
                          <button onClick={remove} className="text-sm text-red-600 hover:underline">
                            Delete
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  {error && <p className="text-sm text-red-600 mb-2">{error}</p>}

                  {note.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-3">
                      {note.tags.map((t) => (
                        <button
                          key={t}
                          onClick={() => onTagClick(t)}
                          className="text-xs px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 hover:bg-indigo-100"
                        >
                          #{t}
                        </button>
                      ))}
                    </div>
                  )}

                  {canWrite && mode === 'edit' ? (
                    <NoteEditor
                      value={draft.content_markdown}
                      onChange={(v) => {
                        setDraft((d) => ({ ...d, content_markdown: v }))
                        setDirty(true)
                      }}
                      tags={tags}
                    />
                  ) : (
                    // Prose gets a capped measure — a note read across a
                    // 2560px monitor is unreadable, not impressive.
                    <div className="reading-col">
                      <NoteMarkdown
                        source={dirty ? draft.content_markdown : note.content_markdown}
                        links={note.links}
                        onTagClick={onTagClick}
                        onEntityClick={onEntityClick}
                      />
                    </div>
                  )}
                  {dirty && mode === 'preview' && (
                    <p className="text-xs text-amber-600 mt-2">
                      Unsaved changes — tags and links are re-indexed when you save.
                    </p>
                  )}
                </div>

                <BacklinksPanel backlinks={backlinks} onOpen={selectNote} />
              </>
            )}
          </section>
        </div>
      )}
    </div>
  )
}

function BacklinksPanel({ backlinks, onOpen }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <h4 className="text-sm font-semibold text-gray-700 mb-2">Backlinks</h4>
      {backlinks.length === 0 ? (
        <p className="text-sm text-gray-400">No other note links here yet.</p>
      ) : (
        <ul className="space-y-2">
          {backlinks.map((b) => (
            <li key={b.id}>
              <button onClick={() => onOpen(b.id)} className="text-sm text-indigo-600 hover:underline">
                {b.title}
              </button>
              {b.excerpt && <div className="text-xs text-gray-400 truncate">{b.excerpt}</div>}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
