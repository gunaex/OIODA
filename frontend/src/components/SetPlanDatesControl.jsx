import { useEffect, useState } from 'react'
import { getPlanDates, setPlanDates } from '../api/client'
import { useAuth } from '../auth/AuthContext.jsx'

// "Set Plan Dates" for a Function or Board Item — the entities that have no
// Gantt bar of their own. Writes baseline_start/baseline_end through
// PUT /plan-dates, which upserts the gantt_items row behind the scenes.
//
// Tasks deliberately don't get this control: their baseline is already set
// from the Gantt bar chart, and having two places to edit the same field
// would just invite them to disagree.
export default function SetPlanDatesControl({ slug, entityType, entityId, onSaved }) {
  const { user } = useAuth()
  const canWrite = user?.role !== 'client_viewer'

  const [form, setForm] = useState({ baseline_start: '', baseline_end: '' })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    setLoading(true)
    setError(null)
    getPlanDates(slug, entityType, entityId)
      .then((data) =>
        setForm({ baseline_start: data?.baseline_start || '', baseline_end: data?.baseline_end || '' }),
      )
      .catch(() => setError('Could not load plan dates.'))
      .finally(() => setLoading(false))
  }, [slug, entityType, entityId])

  const save = async () => {
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      await setPlanDates(slug, {
        entity_type: entityType,
        entity_id: entityId,
        baseline_start: form.baseline_start || null,
        baseline_end: form.baseline_end || null,
      })
      setSaved(true)
      onSaved?.()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not save plan dates.')
    } finally {
      setSaving(false)
    }
  }

  const set = (key) => (e) => {
    setForm((f) => ({ ...f, [key]: e.target.value }))
    setSaved(false)
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6">
      <h3 className="text-sm font-semibold text-gray-700 mb-1">Plan Dates</h3>
      <p className="text-xs text-gray-500 mb-3">
        The planned start/finish this item is measured against in the Progress Matrix. Actual dates are derived
        from status changes — they're never typed in here.
      </p>
      {loading ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : (
        <>
          {error && <p className="text-sm text-red-600 mb-2">{error}</p>}
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Plan Start</label>
              <input
                type="date"
                value={form.baseline_start}
                onChange={set('baseline_start')}
                disabled={!canWrite}
                className="border border-gray-300 rounded px-2 py-1 text-sm disabled:bg-gray-50"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Plan End</label>
              <input
                type="date"
                value={form.baseline_end}
                onChange={set('baseline_end')}
                disabled={!canWrite}
                className="border border-gray-300 rounded px-2 py-1 text-sm disabled:bg-gray-50"
              />
            </div>
            {canWrite && (
              <button
                onClick={save}
                disabled={saving || (!form.baseline_start && !form.baseline_end)}
                className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
              >
                {saving ? 'Saving…' : saved ? 'Saved' : 'Save Plan Dates'}
              </button>
            )}
          </div>
        </>
      )}
    </div>
  )
}
