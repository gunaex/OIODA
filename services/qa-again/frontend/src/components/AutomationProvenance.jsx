import { useEffect, useState } from 'react'
import { getHybridRun, hybridRunEvidenceUrl, listHybridRuns } from '../api/client'
import StatusBadge from './StatusBadge.jsx'

const FIELD_LABELS = [
  ['runner_label', 'Runner'],
  ['runner_version', 'Runner Version'],
  ['browser_name', 'Browser'],
  ['browser_version', 'Browser Version'],
  ['environment', 'Environment'],
  ['artifact_ref', 'Artifact / Build'],
]

/**
 * QA-E8.4/E8.5 — compact automation provenance for a test result, shown
 * only when a HybridRun actually references this cycle_test_result_id
 * (QA-E7). Renders nothing for the common case of a manually-executed
 * result. Never shows a row with no value — an empty field is omitted,
 * not displayed as blank (no meaningless empty rows).
 */
export default function AutomationProvenance({ slug, resultId }) {
  const [runs, setRuns] = useState([])
  const [details, setDetails] = useState({})

  useEffect(() => {
    let cancelled = false
    setRuns([])
    setDetails({})
    listHybridRuns(slug, { cycle_test_result_id: resultId })
      .then((list) => {
        if (cancelled) return
        setRuns(list)
        list.forEach((run) => {
          getHybridRun(slug, run.id).then((full) => {
            if (cancelled) return
            setDetails((prev) => ({ ...prev, [run.id]: full }))
          })
        })
      })
      .catch(() => {
        if (!cancelled) setRuns([])
      })
    return () => {
      cancelled = true
    }
  }, [slug, resultId])

  if (runs.length === 0) return null

  return (
    <div className="border border-gray-200 rounded-lg p-3 space-y-3">
      <p className="text-xs font-medium text-gray-500 uppercase">Automation</p>
      {runs.map((run) => {
        const detail = details[run.id]
        return (
          <div key={run.id} className="text-xs text-gray-700 space-y-1.5">
            <div className="flex items-center gap-2 flex-wrap">
              <StatusBadge status={run.status} />
              <span className="text-gray-400">
                {run.ended_at ? new Date(run.ended_at).toLocaleString() : new Date(run.started_at).toLocaleString()}
              </span>
            </div>
            <dl className="grid grid-cols-2 gap-x-3 gap-y-0.5">
              {FIELD_LABELS.filter(([key]) => run[key]).map(([key, label]) => (
                <div key={key} className="flex gap-1">
                  <dt className="text-gray-400">{label}:</dt>
                  <dd className="text-gray-700">{run[key]}</dd>
                </div>
              ))}
            </dl>
            {detail?.evidence?.length > 0 && (
              <div className="flex gap-2 flex-wrap pt-1">
                {detail.evidence.map((e) => (
                  <a
                    key={e.id}
                    href={hybridRunEvidenceUrl(slug, run.id, e.id)}
                    target="_blank"
                    rel="noreferrer"
                    className="text-emerald-700 hover:underline"
                  >
                    {e.original_filename}
                  </a>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
