import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  calculateEffort,
  createEffortEstimate,
  deleteEffortEstimate,
  getEffortConfig,
  getEffortDrivers,
  listEffortEstimates,
  updateEffortEstimate,
} from '../api/client'
import { useAuth } from '../auth/AuthContext.jsx'

// Function Point effort calculator. The driver list and every coefficient
// come from the backend (which reads them from the same table it calculates
// with), so this form can't drift from the model.
//
// The preview is a real server calculation, debounced — not a second copy of
// the formula living in the browser. There is exactly one implementation of
// the arithmetic and it is the one that was checked against the customer's
// spreadsheets.

const WORK_TYPE_LABELS = { screen: 'Screen', batch: 'Batch', report: 'Report' }
const GROUP_LABELS = { dr: 'DR', pu: 'DN&PU', st: 'IFT/BCT' }
const DEBOUNCE_MS = 300

const fmt = (n, digits = 2) => (n == null ? '—' : Number(n).toFixed(digits))

export default function EffortCalculator({ slug, entityType, entityId }) {
  const { user } = useAuth()
  const canWrite = user?.role !== 'client_viewer'

  const [schema, setSchema] = useState(null)
  const [estimates, setEstimates] = useState([])
  const [editingId, setEditingId] = useState(null)
  const [workType, setWorkType] = useState('screen')
  const [counts, setCounts] = useState({})
  const [complexity, setComplexity] = useState('')
  const [priority, setPriority] = useState('M')
  const [nonSimMode, setNonSimMode] = useState('default') // default | derived | manual
  const [manualNonSim, setManualNonSim] = useState('')
  const [reusability, setReusability] = useState({})
  const [deliveryMode, setDeliveryMode] = useState('human')
  const [showLeverage, setShowLeverage] = useState(false)
  const [config, setConfig] = useState(null)
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [showDrivers, setShowDrivers] = useState(true)
  const debounceRef = useRef(null)

  const loadEstimates = useCallback(
    () => listEffortEstimates(slug, entityType, entityId).then(setEstimates).catch(() => setEstimates([])),
    [slug, entityType, entityId],
  )

  useEffect(() => {
    setLoading(true)
    Promise.all([getEffortDrivers(slug), getEffortConfig(slug), loadEstimates()])
      .then(([s, cfg]) => {
        setSchema(s)
        setConfig(cfg)
        // A restricted project can never be in HUMAN-in-LOOP, so don't let the
        // form start there even if something else set it.
        if (cfg?.hil_restricted) setDeliveryMode('human')
      })
      .catch(() => setError('Could not load the effort calculator.'))
      .finally(() => setLoading(false))
  }, [slug, loadEstimates])

  const drivers = useMemo(
    () => schema?.work_types.find((w) => w.key === workType)?.drivers || [],
    [schema, workType],
  )

  const payload = useMemo(() => {
    const body = { work_type: workType, driver_counts: {}, priority, delivery_mode: deliveryMode }
    for (const [key, value] of Object.entries(counts)) {
      if (value !== '' && value != null) body.driver_counts[key] = Number(value)
    }
    if (complexity !== '') body.complexity = Number(complexity)
    if (nonSimMode === 'manual' && manualNonSim !== '') body.non_similarity = Number(manualNonSim)
    if (nonSimMode === 'derived') body.reusability = reusability
    return body
  }, [workType, counts, complexity, priority, nonSimMode, manualNonSim, reusability, deliveryMode])

  // Debounced live preview — the form recalculates as you type without
  // needing a Save first.
  useEffect(() => {
    if (!schema) return undefined
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      calculateEffort(slug, payload)
        .then(setPreview)
        .catch(() => setPreview(null))
    }, DEBOUNCE_MS)
    return () => clearTimeout(debounceRef.current)
  }, [slug, payload, schema])

  const resetForm = () => {
    setEditingId(null)
    setCounts({})
    setComplexity('')
    setPriority('M')
    setNonSimMode('default')
    setManualNonSim('')
    setReusability({})
    setDeliveryMode('human')
  }

  const startEdit = (estimate) => {
    setEditingId(estimate.id)
    setWorkType(estimate.work_type)
    setCounts(Object.fromEntries(Object.entries(estimate.driver_counts || {}).map(([k, v]) => [k, String(v)])))
    setComplexity(estimate.complexity != null && estimate.complexity !== 1 ? String(estimate.complexity) : '')
    setPriority(estimate.priority || 'M')
    setDeliveryMode(estimate.delivery_mode || 'human')
    if (estimate.non_similarity_source === 'derived') {
      setNonSimMode('derived')
      setReusability(estimate.reusability || {})
    } else if (estimate.non_similarity_source === 'manual') {
      setNonSimMode('manual')
      setManualNonSim(String(estimate.non_similarity))
    } else {
      setNonSimMode('default')
    }
  }

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      if (editingId) {
        await updateEffortEstimate(slug, editingId, payload)
      } else {
        await createEffortEstimate(slug, { ...payload, linked_entity_type: entityType, linked_entity_id: entityId })
      }
      resetForm()
      await loadEstimates()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not save this estimate.')
    } finally {
      setSaving(false)
    }
  }

  const remove = async (id) => {
    if (!confirm('Delete this effort estimate?')) return
    await deleteEffortEstimate(slug, id)
    if (editingId === id) resetForm()
    loadEstimates()
  }

  if (loading) return <div className="bg-white border border-gray-200 rounded-lg p-6 text-sm text-gray-400">Loading…</div>
  if (!schema) return <div className="bg-white border border-gray-200 rounded-lg p-6 text-sm text-red-600">{error}</div>

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-1">
        <h3 className="text-sm font-semibold text-gray-700">Estimate Effort</h3>
        <div className="flex items-center gap-2">
          {['screen', 'batch', 'report'].map((t) => (
            <button
              key={t}
              onClick={() => {
                setWorkType(t)
                setCounts({})
              }}
              className={`px-3 py-1 text-sm rounded-md border ${
                workType === t ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
              }`}
            >
              {WORK_TYPE_LABELS[t]}
            </button>
          ))}
        </div>
      </div>
      <p className="text-xs text-gray-500 mb-4">
        Function Point model, transcribed from the customer's spreadsheet and verified against it. Only the
        drivers for the selected work type are shown.
      </p>

      {error && <p className="text-sm text-red-600 mb-3">{error}</p>}

      {/* Existing saved estimates */}
      {estimates.length > 0 && (
        <div className="mb-4 border border-gray-100 rounded-lg divide-y divide-gray-100">
          {estimates.map((e) => (
            <div key={e.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm">
              <span>
                <span className="text-gray-500">{WORK_TYPE_LABELS[e.work_type]}</span>{' '}
                <span className="font-medium text-gray-900">{fmt(e.calculated_man_days)} MD</span>
                <span className="text-gray-400">
                  {' '}
                  · FP {fmt(e.calculated_fp)} · MM {fmt(e.calculated_mm)}
                  {e.delivery_mode === 'human_in_loop' && (
                    <> · HUMAN-in-LOOP (was {fmt(e.man_days_human)} MD)</>
                  )}
                  {e.priority !== 'M' && <> · priority {e.priority} (not counted)</>}
                </span>
              </span>
              {canWrite && (
                <span className="flex gap-3">
                  <button onClick={() => startEdit(e)} className="text-indigo-600 hover:underline">
                    Edit
                  </button>
                  <button onClick={() => remove(e.id)} className="text-red-600 hover:underline">
                    Delete
                  </button>
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {/* ---- inputs ---- */}
        <div>
          <button
            onClick={() => setShowDrivers((v) => !v)}
            className="text-xs font-semibold text-gray-500 uppercase mb-2 hover:text-gray-700"
          >
            {showDrivers ? '▾' : '▸'} {WORK_TYPE_LABELS[workType]} drivers
          </button>
          {showDrivers && (
            <div className="space-y-1.5 mb-4">
              {drivers.map((d) => (
                <div key={d.key} className="flex items-center gap-2">
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={counts[d.key] ?? ''}
                    onChange={(e) => setCounts((c) => ({ ...c, [d.key]: e.target.value }))}
                    disabled={!canWrite}
                    className="w-16 border border-gray-300 rounded px-2 py-1 text-sm disabled:bg-gray-50"
                  />
                  <span className="text-sm text-gray-700 flex-1">{d.label}</span>
                  <span className="text-[10px] font-mono text-gray-400 shrink-0">
                    {d.divisor ? `⌈n/${d.divisor}⌉` : 'n'} ×{d.coefficient}
                  </span>
                </div>
              ))}
            </div>
          )}

          <div className="flex flex-wrap items-end gap-3 mb-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Complexity</label>
              <input
                type="number"
                step="0.1"
                placeholder="1"
                value={complexity}
                onChange={(e) => setComplexity(e.target.value)}
                disabled={!canWrite}
                className="w-20 border border-gray-300 rounded px-2 py-1 text-sm disabled:bg-gray-50"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Priority</label>
              <input
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                disabled={!canWrite}
                className="w-16 border border-gray-300 rounded px-2 py-1 text-sm disabled:bg-gray-50"
              />
            </div>
            <p className="text-[11px] text-gray-400 flex-1 min-w-[12rem]">
              Only priority “{schema.counted_priority}” counts towards effort — anything else scores 0, matching
              the spreadsheet.
            </p>
          </div>

          {/* Delivery mode */}
          <div className="border border-gray-100 rounded-lg p-3 mb-3">
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <span className="text-xs font-semibold text-gray-500 uppercase">Delivery mode</span>
              {[
                ['human', 'HUMAN'],
                ['human_in_loop', 'HUMAN-in-LOOP'],
              ].map(([key, label]) => {
                const blocked = key === 'human_in_loop' && config?.hil_restricted
                return (
                  <button
                    key={key}
                    onClick={() => !blocked && setDeliveryMode(key)}
                    disabled={!canWrite || blocked}
                    title={
                      blocked
                        ? 'This project is contractually restricted to fully-human delivery.'
                        : undefined
                    }
                    className={`px-2.5 py-0.5 text-xs rounded-full border disabled:opacity-40 disabled:cursor-not-allowed ${
                      deliveryMode === key
                        ? 'bg-gray-800 text-white border-gray-800'
                        : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    {label}
                  </button>
                )
              })}
            </div>
            {config?.hil_restricted && (
              <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1 mt-1">
                This project is contractually restricted to fully-human delivery — check the data-handling
                clause with the client before changing it.{' '}
                <Link to={`/${slug}/settings`} className="underline">
                  Project settings
                </Link>
              </p>
            )}
          </div>

          {/* non-similarity */}
          <div className="border border-gray-100 rounded-lg p-3">
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <span className="text-xs font-semibold text-gray-500 uppercase">Non-similarity</span>
              {[
                ['default', 'New (1.0)'],
                ['derived', 'From reusability'],
                ['manual', 'Enter directly'],
              ].map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setNonSimMode(key)}
                  disabled={!canWrite}
                  className={`px-2 py-0.5 text-xs rounded-full border ${
                    nonSimMode === key
                      ? 'bg-gray-800 text-white border-gray-800'
                      : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            {nonSimMode === 'manual' && (
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={manualNonSim}
                onChange={(e) => setManualNonSim(e.target.value)}
                placeholder="0.00 – 1.00"
                className="w-28 border border-gray-300 rounded px-2 py-1 text-sm"
              />
            )}
            {nonSimMode === 'derived' && (
              <div className="space-y-1">
                <p className="text-[11px] text-gray-400 mb-1">
                  How much of each activity can be reused (0 = all new, 1 = fully reusable).
                </p>
                {schema.non_similarity_activities.map((a) => (
                  <div key={a.key} className="flex items-center gap-2">
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      max="1"
                      value={reusability[a.key] ?? ''}
                      onChange={(e) => setReusability((r) => ({ ...r, [a.key]: Number(e.target.value || 0) }))}
                      disabled={!canWrite}
                      className="w-16 border border-gray-300 rounded px-2 py-1 text-sm disabled:bg-gray-50"
                    />
                    <span className="text-sm text-gray-700 flex-1">{a.label}</span>
                    <span className="text-[10px] font-mono text-gray-400">
                      {GROUP_LABELS[a.group]} w{a.weight}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ---- live preview ---- */}
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Live preview</h4>
          {!preview ? (
            <p className="text-sm text-gray-400">Enter driver counts to see the estimate.</p>
          ) : (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3">
                <Metric label="FP" value={fmt(preview.fp)} />
                <Metric label="Final FP" value={fmt(preview.final_fp)} />
                <Metric label="MM" value={fmt(preview.mm, 3)} />
                <Metric label="Man-days" value={fmt(preview.man_days)} highlight />
              </div>
              <div className="grid grid-cols-3 gap-2 mb-3">
                <Metric label="DR" value={`${fmt(preview.md_dr)} MD`} />
                <Metric label="DN&PU" value={`${fmt(preview.md_dnpu)} MD`} />
                <Metric label="IFT/BCT" value={`${fmt(preview.md_iftbct)} MD`} />
              </div>

              {!preview.counted && (
                <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1 mb-3">
                  {preview.not_counted_reason} — this estimate contributes 0 to every total.
                </p>
              )}

              {/* Side-by-side, so the choice is a comparison rather than a
                  number that silently changed. */}
              {preview.delivery_mode === 'human_in_loop' && preview.leverage_detail && (
                <div className="border border-gray-200 rounded-lg p-3 mb-3 bg-gray-50">
                  <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                    <span className="text-sm text-gray-500">
                      HUMAN: <span className="font-medium text-gray-700">{fmt(preview.man_days_human, 1)} MD</span>
                    </span>
                    <span className="text-sm text-gray-900">
                      HUMAN-in-LOOP:{' '}
                      <span className="font-semibold text-indigo-700">{fmt(preview.man_days, 1)} MD</span>{' '}
                      <span className="text-green-700">
                        (−{(preview.leverage_detail.total_leverage * 100).toFixed(0)}%)
                      </span>
                    </span>
                  </div>
                  {/* Effort and price are separate decisions, and the UI has to
                      say so — otherwise they get read as the same number. */}
                  <p className="text-xs text-gray-600 mt-1">
                    Effort −{(preview.leverage_detail.total_leverage * 100).toFixed(0)}% · price discount{' '}
                    {config?.hil_price_discount_percent ?? 35}% (set separately — a commercial decision, not a
                    consequence of the effort saving)
                  </p>
                  <button
                    onClick={() => setShowLeverage((v) => !v)}
                    className="text-xs text-indigo-600 hover:underline mt-1"
                  >
                    {showLeverage ? 'Hide breakdown' : 'Where does the saving come from?'}
                  </button>
                  {showLeverage && (
                    <>
                      <div className="table-scroll mt-2">
                      <table className="w-full text-xs">
                        <tbody>
                          {preview.leverage_detail.activities.map((a) => (
                            <tr key={a.key} className="border-b border-gray-100 last:border-0">
                              <td className="py-0.5 text-gray-700">{a.label}</td>
                              <td className="py-0.5 text-right font-mono text-gray-400">
                                w{a.weight} × {(a.leverage * 100).toFixed(0)}%
                              </td>
                              <td className="py-0.5 text-right w-12 text-gray-600">
                                {GROUP_LABELS[a.group]}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      </div>
                      <div className="flex flex-wrap gap-x-4 mt-2 text-xs text-gray-600">
                        {preview.leverage_detail.phases.map((p) => (
                          <span key={p.group}>
                            {GROUP_LABELS[p.group]} {(p.phase_leverage * 100).toFixed(0)}%
                          </span>
                        ))}
                      </div>
                      <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1 mt-2">
                        {preview.leverage_detail.calibration_note}
                      </p>
                    </>
                  )}
                </div>
              )}

              <p className="text-[11px] text-gray-400 mb-2">
                non-similarity {fmt(preview.non_similarity, 4)} ({preview.non_similarity_source}) · productivity{' '}
                {preview.productivity_used} · {preview.working_days_per_month} days/month
              </p>

              {/* Where the number came from — the part that gets shown to a client */}
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">Where the FP came from</h4>
              <div className="table-scroll">
              <table className="w-full text-xs">
                <tbody>
                  {preview.breakdown
                    .filter((b) => b.count !== 0)
                    .map((b) => (
                      <tr key={b.key} className="border-b border-gray-50 last:border-0">
                        <td className="py-0.5 text-gray-700">{b.label}</td>
                        <td className="py-0.5 text-right font-mono text-gray-400">{b.rule}</td>
                        <td className="py-0.5 text-right font-medium text-gray-900 w-14">
                          {b.contribution.toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  {preview.breakdown.every((b) => b.count === 0) && (
                    <tr>
                      <td className="py-1 text-gray-400">No drivers entered yet.</td>
                    </tr>
                  )}
                </tbody>
              </table>
              </div>

              {preview.non_similarity_detail && (
                <>
                  <h4 className="text-xs font-semibold text-gray-500 uppercase mt-3 mb-1">
                    Non-similarity derivation
                  </h4>
                  <div className="table-scroll">
                  <table className="w-full text-xs">
                    <tbody>
                      {preview.non_similarity_detail.groups.map((g) => (
                        <tr key={g.group} className="border-b border-gray-50 last:border-0">
                          <td className="py-0.5 text-gray-700">{GROUP_LABELS[g.group]}</td>
                          <td className="py-0.5 text-right font-mono text-gray-400">
                            {g.raw_total.toFixed(3)} × {g.group_weight}
                          </td>
                          <td className="py-0.5 text-right font-medium text-gray-900 w-14">
                            {g.weighted.toFixed(4)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  </div>
                </>
              )}
            </>
          )}

          {canWrite && (
            <div className="flex gap-2 mt-4">
              <button
                onClick={save}
                disabled={saving}
                className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
              >
                {saving ? 'Saving…' : editingId ? 'Update estimate' : 'Save estimate'}
              </button>
              {editingId && (
                <button
                  onClick={resetForm}
                  className="px-3 py-1.5 text-sm text-gray-600 border border-gray-200 rounded-md hover:bg-gray-50"
                >
                  Cancel
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function Metric({ label, value, highlight }) {
  return (
    <div className={`rounded-lg px-2 py-1.5 ${highlight ? 'bg-indigo-50' : 'bg-gray-50'}`}>
      <div className="text-[10px] uppercase tracking-wide text-gray-400">{label}</div>
      <div className={`text-sm font-semibold ${highlight ? 'text-indigo-700' : 'text-gray-900'}`}>{value}</div>
    </div>
  )
}
