import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  addCrImpact,
  createChangeRequest,
  crImpactExportUrl,
  deleteChangeRequest,
  deleteCrImpact,
  getCrImpact,
  listChangeRequests,
  listCrImpacts,
  listItems,
  submitCrForApproval,
  updateChangeRequest,
} from '../api/client'
import { useAuth } from '../auth/AuthContext.jsx'
import EffortCalculator from '../components/EffortCalculator.jsx'

// Change Request log with the four-part impact panel. Every number in that
// panel comes from the backend with its basis attached; anything the backend
// could not compute is shown as "not available" plus what is missing, never
// as a zero.

const STATUSES = ['Draft', 'UnderAnalysis', 'PendingApproval', 'Approved', 'Rejected', 'Deferred']
const STATUS_STYLES = {
  Draft: 'bg-gray-100 text-gray-700',
  UnderAnalysis: 'bg-blue-100 text-blue-700',
  PendingApproval: 'bg-amber-100 text-amber-800',
  Approved: 'bg-green-100 text-green-700',
  Rejected: 'bg-red-100 text-red-700',
  Deferred: 'bg-purple-100 text-purple-700',
}
const IMPACT_TYPES = ['new', 'modify', 'delete']
const emptyForm = { title: '', description: '', requested_by: '', requested_date: '', target_date: '' }
const fmt = (n, d = 1) => (n == null ? null : Number(n).toFixed(d))

export default function ChangeRequestPage() {
  const { slug } = useParams()
  const { user } = useAuth()
  const canWrite = user?.role !== 'client_viewer'

  const [items, setItems] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [error, setError] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    setLoadError(null)
    listChangeRequests(slug)
      .then((rows) => {
        setItems(rows)
        setSelectedId((cur) => (cur && rows.some((r) => r.id === cur) ? cur : rows[0]?.id ?? null))
      })
      .catch(() => setLoadError('Could not load change requests — the backend may be unreachable.'))
      .finally(() => setLoading(false))
  }, [slug])

  useEffect(load, [load])

  const create = async () => {
    if (!form.title.trim()) return
    setError(null)
    try {
      const created = await createChangeRequest(slug, {
        ...form,
        requested_date: form.requested_date || null,
        target_date: form.target_date || null,
      })
      setAdding(false)
      setForm(emptyForm)
      await load()
      setSelectedId(created.id)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not create the change request.')
    }
  }

  const selected = items.find((i) => i.id === selectedId) || null

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Change Requests</h2>
          <p className="text-xs text-gray-500">
            Every request carries its own effort, budget, schedule and cost impact — priced before it is agreed.
          </p>
        </div>
        {canWrite && (
          <button
            onClick={() => setAdding((a) => !a)}
            className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
          >
            + New CR
          </button>
        )}
      </div>

      {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
      {loadError && (
        <p className="text-sm text-red-600 mb-3">
          {loadError}{' '}
          <button onClick={load} className="underline font-medium">
            Retry
          </button>
        </p>
      )}

      {adding && (
        <div className="mb-4 p-4 bg-white border border-gray-200 rounded-lg flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-xs text-gray-500 mb-1">Title</label>
            <input
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Requested by</label>
            <input
              value={form.requested_by}
              onChange={(e) => setForm((f) => ({ ...f, requested_by: e.target.value }))}
              className="w-32 border border-gray-300 rounded px-2 py-1 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Requested date</label>
            <input
              type="date"
              value={form.requested_date}
              onChange={(e) => setForm((f) => ({ ...f, requested_date: e.target.value }))}
              className="border border-gray-300 rounded px-2 py-1 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Target date</label>
            <input
              type="date"
              value={form.target_date}
              onChange={(e) => setForm((f) => ({ ...f, target_date: e.target.value }))}
              className="border border-gray-300 rounded px-2 py-1 text-sm"
            />
          </div>
          <div className="flex-1 min-w-[200px]">
            <label className="block text-xs text-gray-500 mb-1">Description</label>
            <input
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
            />
          </div>
          <button onClick={create} className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700">
            Create
          </button>
        </div>
      )}

      {loading ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-gray-400">No change requests yet.</p>
      ) : (
        <div className="flex flex-col lg:flex-row gap-4">
          <aside className="lg:w-72 shrink-0 bg-white border border-gray-200 rounded-lg divide-y divide-gray-100 max-h-[36rem] overflow-y-auto">
            {items.map((cr) => (
              <button
                key={cr.id}
                onClick={() => setSelectedId(cr.id)}
                className={`w-full text-left px-3 py-2 ${cr.id === selectedId ? 'bg-indigo-50' : 'hover:bg-gray-50'}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs text-gray-500">{cr.cr_code}</span>
                  <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${STATUS_STYLES[cr.status]}`}>
                    {cr.status}
                  </span>
                </div>
                <div className="text-sm font-medium text-gray-900 truncate">{cr.title}</div>
                {cr.target_date && <div className="text-xs text-gray-400">target {cr.target_date}</div>}
              </button>
            ))}
          </aside>

          <section className="flex-1 min-w-0 space-y-4">
            {selected && (
              <CrDetail
                key={selected.id}
                slug={slug}
                cr={selected}
                canWrite={canWrite}
                onChanged={load}
                onDeleted={() => {
                  setSelectedId(null)
                  load()
                }}
              />
            )}
          </section>
        </div>
      )}
    </div>
  )
}

function CrDetail({ slug, cr, canWrite, onChanged, onDeleted }) {
  const [impacts, setImpacts] = useState([])
  const [analysis, setAnalysis] = useState(null)
  const [functions, setFunctions] = useState([])
  const [impactForm, setImpactForm] = useState({ impact_type: 'modify', linked_function_id: '', function_name: '', note: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const reload = useCallback(() => {
    setError(null)
    Promise.all([listCrImpacts(slug, cr.id), getCrImpact(slug, cr.id)])
      .then(([i, a]) => {
        setImpacts(i)
        setAnalysis(a)
      })
      .catch(() => setError('Could not load this change request.'))
  }, [slug, cr.id])

  useEffect(reload, [reload])
  useEffect(() => {
    listItems(slug, 'functions').then(setFunctions).catch(() => setFunctions([]))
  }, [slug])

  const act = async (fn) => {
    setBusy(true)
    setError(null)
    try {
      await fn()
      reload()
      onChanged()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Action failed.')
    } finally {
      setBusy(false)
    }
  }

  const addImpact = () =>
    act(async () => {
      await addCrImpact(slug, cr.id, {
        ...impactForm,
        linked_function_id: impactForm.linked_function_id ? Number(impactForm.linked_function_id) : null,
        function_name: impactForm.function_name || null,
      })
      setImpactForm({ impact_type: 'modify', linked_function_id: '', function_name: '', note: '' })
    })

  return (
    <>
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
          <div>
            <div className="text-xs text-gray-500">{cr.cr_code}</div>
            <h3 className="text-lg font-semibold text-gray-900">{cr.title}</h3>
            <div className="text-sm text-gray-500 mt-1">
              {cr.requested_by || 'unassigned'}
              {cr.requested_date && <> · requested {cr.requested_date}</>}
              {cr.target_date && <> · target {cr.target_date}</>}
            </div>
          </div>
          <span className={`px-2 py-0.5 rounded-full text-xs ${STATUS_STYLES[cr.status]}`}>{cr.status}</span>
        </div>
        {cr.description && (
          <p className="reading-col text-sm text-gray-700 mb-3 whitespace-pre-wrap">{cr.description}</p>
        )}
        {error && <p className="text-sm text-red-600 mb-3">{error}</p>}

        {canWrite && (
          <div className="flex flex-wrap items-center gap-2">
            <select
              value=""
              onChange={(e) => e.target.value && act(() => updateChangeRequest(slug, cr.id, { status: e.target.value }))}
              disabled={busy}
              className="text-sm border border-gray-300 rounded-md px-2 py-1.5"
            >
              <option value="">Change status…</option>
              {STATUSES.filter((s) => s !== cr.status).map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
            <button
              onClick={() => act(() => submitCrForApproval(slug, cr.id))}
              disabled={busy}
              className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
            >
              Submit for Approval
            </button>
            <a
              href={crImpactExportUrl(slug, cr.id)}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Export Impact Analysis
            </a>
            <button
              onClick={() => confirm('Delete this change request?') && act(() => deleteChangeRequest(slug, cr.id).then(onDeleted))}
              className="text-sm text-red-600 hover:underline ml-auto"
            >
              Delete
            </button>
          </div>
        )}
        {cr.linked_document_id && (
          <p className="text-xs text-gray-500 mt-3">
            Impact Analysis document #{cr.linked_document_id} — approval is blocked until it is Confirmed through
            the normal document sign-off.
          </p>
        )}
      </div>

      {analysis && <ImpactPanel analysis={analysis} />}

      {/* impacted functions */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h4 className="text-sm font-semibold text-gray-700 mb-3">Function Impact</h4>
        {impacts.length === 0 ? (
          <p className="text-sm text-gray-400 mb-3">No impacted functions recorded yet.</p>
        ) : (
          <div className="table-scroll mb-3">
          <table className="w-full min-w-[34rem] text-sm">
            <thead className="text-left text-gray-500 text-xs uppercase">
              <tr>
                <th className="py-1">Function</th>
                <th className="py-1">Type</th>
                <th className="py-1">Note</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {impacts.map((i) => (
                <tr key={i.id} className="border-t border-gray-100">
                  <td className="py-1.5">
                    {i.function_name || '(unnamed)'}
                    {i.linked_function_id ? (
                      <span className="text-xs text-gray-400"> · #{i.linked_function_id}</span>
                    ) : (
                      <span className="text-xs text-amber-600"> · to be created on approval</span>
                    )}
                  </td>
                  <td className="py-1.5 capitalize">{i.impact_type}</td>
                  <td className="py-1.5 text-gray-600">{i.note}</td>
                  <td className="py-1.5 text-right">
                    {canWrite && (
                      <button
                        onClick={() => act(() => deleteCrImpact(slug, cr.id, i.id))}
                        className="text-xs text-red-600 hover:underline"
                      >
                        Remove
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}

        {canWrite && (
          <div className="flex flex-wrap items-end gap-2">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Type</label>
              <select
                value={impactForm.impact_type}
                onChange={(e) => setImpactForm((f) => ({ ...f, impact_type: e.target.value }))}
                className="border border-gray-300 rounded px-2 py-1 text-sm capitalize"
              >
                {IMPACT_TYPES.map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Existing function</label>
              <select
                value={impactForm.linked_function_id}
                onChange={(e) => {
                  const id = e.target.value
                  const fn = functions.find((f) => String(f.id) === id)
                  setImpactForm((f) => ({ ...f, linked_function_id: id, function_name: fn ? fn.name : f.function_name }))
                }}
                className="border border-gray-300 rounded px-2 py-1 text-sm max-w-[14rem]"
              >
                <option value="">(new — not yet in the list)</option>
                {functions.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.function_code ? `${f.function_code} ` : ''}
                    {f.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex-1 min-w-[10rem]">
              <label className="block text-xs text-gray-500 mb-1">Function name</label>
              <input
                value={impactForm.function_name}
                onChange={(e) => setImpactForm((f) => ({ ...f, function_name: e.target.value }))}
                className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
              />
            </div>
            <div className="flex-1 min-w-[10rem]">
              <label className="block text-xs text-gray-500 mb-1">Note</label>
              <input
                value={impactForm.note}
                onChange={(e) => setImpactForm((f) => ({ ...f, note: e.target.value }))}
                className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
              />
            </div>
            <button
              onClick={addImpact}
              disabled={busy}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
            >
              Add
            </button>
          </div>
        )}
      </div>

      <EffortCalculator slug={slug} entityType="change_request" entityId={cr.id} />
    </>
  )
}

function ImpactPanel({ analysis }) {
  const { effort, budget, schedule, cost } = analysis
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6">
      <h4 className="text-sm font-semibold text-gray-700 mb-3">Impact</h4>
      <div className="grid gap-4 sm:grid-cols-2">
        <Section title="Effort" missing={effort.missing}>
          {effort.total_md != null && (
            <>
              <Big>{fmt(effort.total_md, 2)} MD</Big>
              <Rows
                rows={[
                  ['DR', `${fmt(effort.dr, 2)} MD`],
                  ['DN&PU', `${fmt(effort.dnpu, 2)} MD`],
                  ['IFT/BCT', `${fmt(effort.iftbct, 2)} MD`],
                ]}
              />
            </>
          )}
        </Section>

        <Section title="Budget" missing={budget.missing}>
          {budget.remaining_after != null && (
            <>
              <Big>
                {fmt(budget.remaining_after)} MD left
                {budget.remaining_percent_after != null && (
                  <span className="text-gray-400 text-base font-normal"> ({fmt(budget.remaining_percent_after)}%)</span>
                )}
              </Big>
              <Rows
                rows={[
                  ['Contracted', `${fmt(budget.contracted_md, 0)} MD`],
                  ['Used', `${fmt(budget.used_md)} MD`],
                  ['Remaining before', `${fmt(budget.remaining_before)} MD`],
                ]}
              />
              {budget.warning && (
                <p className="mt-2 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded px-2 py-1">
                  {budget.warning}
                </p>
              )}
            </>
          )}
        </Section>

        <Section title="Schedule" missing={schedule.missing}>
          {schedule.estimated_delay_days != null && (
            <>
              <Big>+{schedule.estimated_delay_days} days</Big>
              <p className="text-xs text-gray-500 mt-1">{schedule.basis}</p>
            </>
          )}
          {schedule.affected_phases?.length > 0 && (
            <p className="text-xs text-gray-500 mt-1">Affects {schedule.affected_phases.join(', ')}</p>
          )}
          <DataPoints points={schedule.data_points} />
        </Section>

        <Section title="Cost" missing={cost.missing}>
          {cost.estimated_thb != null && (
            <>
              <Big>{Number(cost.estimated_thb).toLocaleString()} THB</Big>
              <p className="text-xs text-gray-500 mt-1">{cost.basis}</p>
            </>
          )}
          <DataPoints points={cost.data_points} />
        </Section>
      </div>
    </div>
  )
}

// Anything the config page can actually fix gets a link straight to the
// field, rather than printing a column name for the reader to go and find.
const SETTINGS_FIELDS = {
  'effort_estimate_config.contracted_total_md': 'contracted_total_md',
  'effort_estimate_config.rate_thb_per_md': 'rate_thb_per_md',
}

// A section with nothing to report says so, and says what is missing — it
// never renders a 0 that could be mistaken for a real answer.
function Section({ title, missing, children }) {
  const { slug } = useParams()
  const hasContent = Array.isArray(children) ? children.some(Boolean) : Boolean(children)
  return (
    <div className="border border-gray-100 rounded-lg p-3">
      <div className="text-xs font-semibold text-gray-500 uppercase mb-1">{title}</div>
      {hasContent ? (
        children
      ) : (
        <>
          <p className="text-sm text-gray-400">Not available yet.</p>
          {missing?.length > 0 && (
            <ul className="mt-1 text-xs text-gray-400 list-disc list-inside space-y-0.5">
              {missing.map((m) => {
                const field = SETTINGS_FIELDS[m]
                return (
                  <li key={m}>
                    needs {m}
                    {field && (
                      <>
                        {' '}
                        <Link
                          to={`/${slug}/settings?field=${field}`}
                          className="text-indigo-600 hover:underline"
                        >
                          set it →
                        </Link>
                      </>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </>
      )}
    </div>
  )
}

const Big = ({ children }) => <div className="text-xl font-semibold text-gray-900">{children}</div>

const Rows = ({ rows }) => (
  <div className="table-scroll mt-1">
  <table className="w-full text-xs">
    <tbody>
      {rows.map(([k, v]) => (
        <tr key={k}>
          <td className="text-gray-500 py-0.5">{k}</td>
          <td className="text-right font-medium text-gray-800">{v}</td>
        </tr>
      ))}
    </tbody>
  </table>
  </div>
)

const DataPoints = ({ points }) =>
  points?.length ? (
    <div className="flex flex-wrap gap-1 mt-2">
      {points.map((p) => (
        <span key={p} className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 font-mono">
          {p}
        </span>
      ))}
    </div>
  ) : null
