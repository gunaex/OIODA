import { useEffect, useMemo, useState } from 'react'
import { NavLink, useParams } from 'react-router-dom'
import {
  getCycle,
  listCycleResults,
  updateCycleResult,
  reviewCycleResult,
  getCycleResultHistory,
  lockCycle,
  reopenCycle,
} from '../api/client'
import { useAuth } from '../auth/AuthContext.jsx'
import StatusBadge from '../components/StatusBadge.jsx'
import EvidenceGallery from '../components/EvidenceGallery.jsx'

const STATUS_FILTERS = ['ALL', 'NOT_RUN', 'PASS', 'FAIL', 'BLOCKED', 'NOT_APPLICABLE']

export default function CycleExecution() {
  const { slug, cycleId } = useParams()
  const { user } = useAuth()
  const canEdit = user?.role === 'ADMIN' || user?.role === 'TESTER'
  const isAdmin = user?.role === 'ADMIN'

  const [cycle, setCycle] = useState(null)
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [filter, setFilter] = useState('ALL')
  // Per-result unsaved draft — keyed by result id so switching cases
  // never loses in-progress typing (rebuild prompt §12 execution screen
  // requirement).
  const [drafts, setDrafts] = useState({})
  const [saveState, setSaveState] = useState({}) // resultId -> 'idle'|'saving'|'saved'|'error'
  const [history, setHistory] = useState(null)
  const [showHistory, setShowHistory] = useState(false)

  const load = () => {
    setLoading(true)
    setError(null)
    Promise.all([getCycle(slug, cycleId), listCycleResults(slug, cycleId)])
      .then(([c, r]) => {
        setCycle(c)
        setResults(r)
        setSelectedId((prev) => prev ?? r[0]?.id ?? null)
      })
      .catch(() => setError('Could not reach the backend.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [slug, cycleId])

  const selected = useMemo(() => results.find((r) => r.id === selectedId) || null, [results, selectedId])
  const draft = selectedId ? drafts[selectedId] || {} : {}
  const isLocked = cycle?.status === 'LOCKED'

  const filteredResults = filter === 'ALL' ? results : results.filter((r) => r.status === filter)

  const updateDraft = (patch) => {
    if (!selectedId) return
    setDrafts((prev) => ({ ...prev, [selectedId]: { ...prev[selectedId], ...patch } }))
  }

  const selectCase = (id) => {
    setSelectedId(id)
    setShowHistory(false)
    setHistory(null)
    setError(null)
  }

  const submitStatus = async (status) => {
    if (!selected) return
    const payload = {
      status,
      actual_result_md: draft.actual_result_md ?? selected.actual_result_md ?? '',
      blocked_reason: draft.blocked_reason ?? selected.blocked_reason ?? '',
      na_reason: draft.na_reason ?? selected.na_reason ?? '',
      defect_reference: draft.defect_reference ?? selected.defect_reference ?? '',
    }
    setSaveState((prev) => ({ ...prev, [selected.id]: 'saving' }))
    setError(null)
    try {
      const updated = await updateCycleResult(slug, cycleId, selected.id, payload)
      setResults((prev) => prev.map((r) => (r.id === updated.id ? updated : r)))
      setDrafts((prev) => ({ ...prev, [selected.id]: undefined }))
      setSaveState((prev) => ({ ...prev, [selected.id]: 'saved' }))
      const refreshedCycle = await getCycle(slug, cycleId)
      setCycle(refreshedCycle)
    } catch (err) {
      setSaveState((prev) => ({ ...prev, [selected.id]: 'error' }))
      setError(err.response?.data?.detail || 'Could not save result')
    }
  }

  const handleReview = async (reviewStatus) => {
    if (!selected) return
    const updated = await reviewCycleResult(slug, cycleId, selected.id, { review_status: reviewStatus })
    setResults((prev) => prev.map((r) => (r.id === updated.id ? updated : r)))
  }

  const toggleHistory = async () => {
    if (!selected) return
    if (!showHistory) {
      const h = await getCycleResultHistory(slug, cycleId, selected.id)
      setHistory(h)
    }
    setShowHistory((v) => !v)
  }

  const handleLock = async () => {
    if (!window.confirm('Lock this cycle? All results become read-only until an admin reopens it.')) return
    const updated = await lockCycle(slug, cycleId)
    setCycle(updated)
  }

  const handleReopen = async () => {
    const reason = window.prompt('Reason for reopening this locked cycle:')
    if (!reason) return
    const updated = await reopenCycle(slug, cycleId, reason)
    setCycle(updated)
  }

  if (loading) return <p className="text-gray-500 text-sm">Loading…</p>
  if (error && !cycle)
    return (
      <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-md px-4 py-3">
        <p>{error}</p>
        <button onClick={load} className="mt-2 text-red-800 font-medium hover:underline">
          Retry
        </button>
      </div>
    )

  const saveLabel = { saving: 'Saving…', saved: 'Saved', error: 'Error saving' }[saveState[selectedId]]

  return (
    <div className="space-y-4">
      <div>
        <NavLink to={`/${slug}/cycles`} className="text-sm text-gray-500 hover:text-gray-800">
          &larr; Test Cycles
        </NavLink>
        <div className="flex items-center gap-2 flex-wrap mt-1">
          <h2 className="text-xl font-semibold text-gray-900">{cycle.name}</h2>
          <StatusBadge status={cycle.status} />
          <span className="text-xs text-gray-500">{cycle.environment}</span>
          {isAdmin && cycle.status !== 'LOCKED' && (
            <button onClick={handleLock} className="ml-auto text-xs border border-gray-300 rounded-md px-2 py-1 hover:bg-gray-50">
              Lock Cycle
            </button>
          )}
          {isAdmin && cycle.status === 'LOCKED' && (
            <button onClick={handleReopen} className="ml-auto text-xs border border-gray-300 rounded-md px-2 py-1 hover:bg-gray-50">
              Reopen (admin)
            </button>
          )}
        </div>
        {isLocked && (
          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-3 py-2 mt-2">
            This cycle is locked — results are read-only. An admin must reopen it to make changes.
          </p>
        )}
        {error && (
          <p className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-md px-3 py-2 mt-2">{error}</p>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4">
        {/* Left panel: case list + filters */}
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <div className="flex flex-wrap gap-1 p-2 border-b border-gray-100">
            {STATUS_FILTERS.map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-2 py-1 text-xs rounded ${filter === f ? 'bg-emerald-600 text-white' : 'text-gray-600 hover:bg-gray-100'}`}
              >
                {f}
              </button>
            ))}
          </div>
          <div className="max-h-[60vh] overflow-y-auto divide-y divide-gray-50">
            {filteredResults.map((r) => (
              <button
                key={r.id}
                onClick={() => selectCase(r.id)}
                className={`w-full text-left px-3 py-2 hover:bg-gray-50 ${selectedId === r.id ? 'bg-emerald-50' : ''}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[11px] text-gray-500">{r.checkpoint_code}</span>
                  <StatusBadge status={r.status} />
                </div>
                <p className="text-xs text-gray-800 mt-0.5 truncate">{r.case_title}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Main panel */}
        {selected && (
          <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-mono text-xs text-gray-500">{selected.checkpoint_code}</span>
                <h3 className="font-medium text-gray-900">{selected.case_title}</h3>
                {selected.case_priority && (
                  <span className="px-1.5 py-0.5 text-[10px] uppercase rounded bg-gray-100 text-gray-500">
                    {selected.case_priority}
                  </span>
                )}
              </div>
            </div>

            {selected.case_setup_md && (
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase">Setup</p>
                <p className="text-sm text-gray-800 whitespace-pre-wrap">{selected.case_setup_md}</p>
              </div>
            )}
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase">Action</p>
              <p className="text-sm text-gray-800 whitespace-pre-wrap">{selected.case_action_md}</p>
            </div>
            {selected.case_validation_md && (
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase">Validation</p>
                <p className="text-sm text-gray-800 whitespace-pre-wrap">{selected.case_validation_md}</p>
              </div>
            )}
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase">Expected Result</p>
              <p className="text-sm text-gray-800 whitespace-pre-wrap">{selected.case_expected_result_md}</p>
            </div>

            <EvidenceGallery
              key={selected.id}
              slug={slug}
              cycleId={cycleId}
              resultId={selected.id}
              canEdit={canEdit}
              isAdmin={isAdmin}
              isLocked={isLocked}
            />

            <div>
              <p className="text-xs font-medium text-gray-500 uppercase mb-1">Actual Result</p>
              <textarea
                disabled={isLocked || !canEdit}
                value={draft.actual_result_md ?? selected.actual_result_md ?? ''}
                onChange={(e) => updateDraft({ actual_result_md: e.target.value })}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:bg-gray-50"
                placeholder="What actually happened (required for FAIL)"
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase mb-1">Blocked Reason</p>
                <input
                  disabled={isLocked || !canEdit}
                  value={draft.blocked_reason ?? selected.blocked_reason ?? ''}
                  onChange={(e) => updateDraft({ blocked_reason: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:bg-gray-50"
                  placeholder="Required for BLOCKED"
                />
              </div>
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase mb-1">N/A Reason</p>
                <input
                  disabled={isLocked || !canEdit}
                  value={draft.na_reason ?? selected.na_reason ?? ''}
                  onChange={(e) => updateDraft({ na_reason: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:bg-gray-50"
                  placeholder="Required for N/A"
                />
              </div>
            </div>

            {selected.status === 'NOT_APPLICABLE' && (
              <div className="flex items-center gap-2 text-xs">
                <span className="text-gray-500">Review:</span>
                <StatusBadge status={selected.review_status} />
                {isAdmin && selected.review_status === 'UNREVIEWED' && (
                  <>
                    <button onClick={() => handleReview('ACCEPTED')} className="text-emerald-600 hover:underline">
                      Accept
                    </button>
                    <button onClick={() => handleReview('CHANGES_REQUESTED')} className="text-red-500 hover:underline">
                      Request changes
                    </button>
                  </>
                )}
              </div>
            )}

            {/* Sticky action area */}
            {canEdit && !isLocked && (
              <div className="sticky bottom-0 bg-white border-t border-gray-100 pt-3 flex items-center gap-2 flex-wrap">
                <button
                  onClick={() => submitStatus('PASS')}
                  className="px-3 py-1.5 text-sm bg-green-600 text-white rounded-md hover:bg-green-700"
                >
                  PASS
                </button>
                <button
                  onClick={() => submitStatus('FAIL')}
                  className="px-3 py-1.5 text-sm bg-red-600 text-white rounded-md hover:bg-red-700"
                >
                  NG
                </button>
                <button
                  onClick={() => submitStatus('BLOCKED')}
                  className="px-3 py-1.5 text-sm bg-amber-500 text-white rounded-md hover:bg-amber-600"
                >
                  BLOCKED
                </button>
                <button
                  onClick={() => submitStatus('NOT_APPLICABLE')}
                  className="px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  N/A
                </button>
                {saveLabel && (
                  <span className={`text-xs ${saveState[selectedId] === 'error' ? 'text-red-600' : 'text-gray-500'}`}>
                    {saveLabel}
                  </span>
                )}
                <button onClick={toggleHistory} className="ml-auto text-xs text-gray-500 hover:underline">
                  {showHistory ? 'Hide history' : 'Show history'}
                </button>
              </div>
            )}
            {(!canEdit || isLocked) && (
              <button onClick={toggleHistory} className="text-xs text-gray-500 hover:underline">
                {showHistory ? 'Hide history' : 'Show history'}
              </button>
            )}

            {showHistory && (
              <div className="border-t border-gray-100 pt-3">
                <p className="text-xs font-medium text-gray-500 uppercase mb-2">Result History</p>
                {!history || history.length === 0 ? (
                  <p className="text-xs text-gray-400">No changes recorded yet.</p>
                ) : (
                  <ul className="space-y-2">
                    {history.map((h) => (
                      <li key={h.id} className="text-xs text-gray-600 border-l-2 border-gray-200 pl-2">
                        <span className="font-medium">rev {h.result_revision_no}</span> — <StatusBadge status={h.status} />{' '}
                        by {h.changed_by} at {new Date(h.changed_at).toLocaleString()}
                        {h.actual_result_md && <div className="text-gray-500 mt-0.5">{h.actual_result_md}</div>}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
