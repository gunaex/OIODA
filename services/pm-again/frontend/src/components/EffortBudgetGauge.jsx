import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getEffortBudget } from '../api/client'
import { useAuth } from '../auth/AuthContext.jsx'

// Fuel-gauge for the contracted effort budget: Used | Committed | Remaining
// as one stacked bar. Present mode blows it up for showing to a client, the
// same idea as the Gantt's Present toggle.

const STATUS_STYLES = {
  healthy: { bar: 'bg-green-500', text: 'text-green-700', chip: 'bg-green-100 text-green-800', label: 'Healthy' },
  warning: { bar: 'bg-amber-500', text: 'text-amber-700', chip: 'bg-amber-100 text-amber-800', label: 'Warning' },
  critical: { bar: 'bg-orange-600', text: 'text-orange-700', chip: 'bg-orange-100 text-orange-800', label: 'Critical' },
  over_budget: { bar: 'bg-red-600', text: 'text-red-700', chip: 'bg-red-100 text-red-800', label: 'Over budget' },
}

const fmt = (n, d = 1) => (n == null ? '—' : Number(n).toFixed(d))

export default function EffortBudgetGauge({ slug, compact = false }) {
  const { user } = useAuth()
  const isPmoAdmin = user?.role === 'pmo_admin'
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [present, setPresent] = useState(false)

  const load = () => {
    setLoading(true)
    setError(null)
    getEffortBudget(slug)
      .then(setData)
      .catch(() => setError('Could not load the effort budget.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [slug])

  if (loading) return compact ? null : <div className="bg-white border border-gray-200 rounded-lg p-4 text-sm text-gray-400">Loading…</div>
  if (error) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-4 text-sm text-red-600">
        {error}{' '}
        <button onClick={load} className="underline font-medium">
          Retry
        </button>
      </div>
    )
  }
  if (!data) return null

  // No contracted figure means there is no budget to draw. Saying "0% left"
  // would be worse than saying nothing.
  if (data.contracted_md == null) {
    if (compact) return null
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-1">Effort Budget</h3>
        <p className="text-sm text-gray-500">{data.note}</p>
        {/* The field it's missing is one click away rather than a name to go
            hunting for. */}
        {isPmoAdmin ? (
          <Link
            to={`/${slug}/settings?field=contracted_total_md`}
            className="inline-block mt-2 px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
          >
            Set contracted man-days →
          </Link>
        ) : (
          <p className="text-xs text-gray-400 mt-1">A PMO admin can set this in Project Settings.</p>
        )}
        <p className="text-xs text-gray-400 mt-2">
          Estimated so far: {fmt(data.used_md)} MD delivered, {fmt(data.committed_md)} MD committed.
        </p>
      </div>
    )
  }

  const style = STATUS_STYLES[data.status] || STATUS_STYLES.healthy
  const contracted = data.contracted_md || 1
  const pct = (v) => Math.max(0, Math.min(100, (v / contracted) * 100))
  const usedPct = pct(data.used_md)
  const committedPct = pct(data.committed_md)
  const remainingPct = Math.max(0, 100 - usedPct - committedPct)
  const overBudget = data.remaining_md < 0

  const bar = (
    <div className={`w-full ${present ? 'h-12' : compact ? 'h-2' : 'h-5'} rounded-full bg-gray-100 overflow-hidden flex`}>
      <div className="bg-gray-500" style={{ width: `${usedPct}%` }} title={`Used ${fmt(data.used_md)} MD`} />
      <div className="bg-amber-400" style={{ width: `${committedPct}%` }} title={`Committed ${fmt(data.committed_md)} MD`} />
      <div className={style.bar} style={{ width: `${remainingPct}%` }} title={`Remaining ${fmt(data.remaining_md)} MD`} />
    </div>
  )

  if (compact) {
    return (
      <div className="mt-2">
        {bar}
        <div className="flex items-center justify-between mt-1">
          <span className="text-[10px] text-gray-400">
            {fmt(data.remaining_md)} / {fmt(data.contracted_md, 0)} MD
          </span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${style.chip}`}>{style.label}</span>
        </div>
      </div>
    )
  }

  const body = (
    <>
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <h3 className={`font-semibold text-gray-800 ${present ? 'text-2xl' : 'text-sm'}`}>Effort Budget</h3>
          <span className={`px-2 py-0.5 rounded-full ${present ? 'text-sm' : 'text-xs'} ${style.chip}`}>
            {style.label}
          </span>
        </div>
        <button
          onClick={() => setPresent((p) => !p)}
          className="px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
        >
          {present ? 'Exit Present' : 'Present'}
        </button>
      </div>

      <p className={`font-semibold ${style.text} ${present ? 'text-5xl mb-4' : 'text-xl mb-2'}`}>
        {fmt(data.remaining_md)} / {fmt(data.contracted_md, 0)} MD
        <span className={`text-gray-400 font-normal ${present ? 'text-2xl' : 'text-sm'}`}>
          {' '}
          ({fmt(data.remaining_percent)}%)
        </span>
      </p>

      {bar}

      <div className={`flex flex-wrap gap-x-6 gap-y-1 mt-3 ${present ? 'text-lg' : 'text-xs'}`}>
        <Legend color="bg-gray-500" label="Used" value={`${fmt(data.used_md)} MD`} />
        <Legend color="bg-amber-400" label="Committed" value={`${fmt(data.committed_md)} MD`} />
        <Legend color={style.bar} label="Remaining" value={`${fmt(data.remaining_md)} MD`} />
      </div>

      {overBudget && (
        <p className={`mt-3 text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2 ${present ? 'text-lg' : 'text-sm'}`}>
          Over the contracted budget by {fmt(Math.abs(data.remaining_md))} MD.
        </p>
      )}
    </>
  )

  if (present) {
    return (
      <div className="fixed inset-0 bg-white z-50 p-10 overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="max-w-4xl mx-auto">{body}</div>
      </div>
    )
  }

  return <div className="bg-white border border-gray-200 rounded-lg p-4">{body}</div>
}

function Legend({ color, label, value }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`w-2.5 h-2.5 rounded-sm ${color}`} />
      <span className="text-gray-500">{label}</span>
      <span className="font-medium text-gray-900">{value}</span>
    </span>
  )
}
