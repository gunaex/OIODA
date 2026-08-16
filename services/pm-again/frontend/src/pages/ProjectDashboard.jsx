import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getProjectDashboard, getSlippageSummary } from '../api/client'
import StatusBadge from '../components/StatusBadge.jsx'
import EffortBudgetGauge from '../components/EffortBudgetGauge.jsx'
import EcosystemSourceBadge from '../components/EcosystemSourceBadge.jsx'

const RAG_LABEL = { red: 'Red', amber: 'Amber', green: 'Green' }

export default function ProjectDashboard() {
  const { slug } = useParams()
  const [data, setData] = useState(null)
  const [slippage, setSlippage] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)

  const load = () => {
    setLoading(true)
    setLoadError(null)
    Promise.all([getProjectDashboard(slug), getSlippageSummary(slug)])
      .then(([d, s]) => {
        setData(d)
        setSlippage(s)
      })
      .catch(() => setLoadError('Could not load the dashboard — the backend may be unreachable.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [slug])

  if (loading) return <p className="text-sm text-gray-400">Loading…</p>
  if (loadError) {
    return (
      <p className="text-sm text-red-600">
        {loadError}{' '}
        <button onClick={load} className="underline font-medium">
          Retry
        </button>
      </p>
    )
  }
  if (!data) return null

  const slippageRows = [
    ...slippage.tasks.map((t) => ({ ...t, kind: 'Task', label: t.name, sortKey: t.gap_score ?? 0 })),
    ...slippage.phases.map((p) => ({ ...p, kind: 'Phase', label: p.phase, sortKey: p.docs_remaining })),
  ].sort((a, b) => b.sortKey - a.sortKey)

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-semibold text-gray-900">Project Dashboard</h2>
        <StatusBadge status={data.rag} />
        <span className="text-sm text-gray-400">{RAG_LABEL[data.rag]}</span>
      </div>

      <EcosystemSourceBadge slug={slug} />

      <EffortBudgetGauge slug={slug} />

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs text-gray-400 uppercase tracking-wide">Overdue Tasks</p>
          <p className="text-2xl font-semibold text-gray-900">{data.overdue_task_count}</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs text-gray-400 uppercase tracking-wide">Overdue Mandatory Docs</p>
          <p className="text-2xl font-semibold text-gray-900">{data.overdue_mandatory_docs}</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-xs text-gray-400 uppercase tracking-wide">Open Critical Incidents</p>
          <p className="text-2xl font-semibold text-gray-900">{data.open_critical_incidents}</p>
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg">
        <h3 className="font-medium text-gray-900 px-4 py-3 border-b border-gray-100">
          ⚠️ Slippage Warning
        </h3>
        <div className="divide-y divide-gray-100">
          {slippageRows.length === 0 ? (
            <p className="px-4 py-4 text-center text-gray-400 text-sm">Nothing at risk right now.</p>
          ) : (
            slippageRows.map((row, i) => (
              <div key={`${row.kind}-${i}`} className="flex items-center justify-between gap-3 px-4 py-3">
                <div className="min-w-0">
                  <p className="text-sm text-gray-900">
                    <span className="text-xs text-gray-400 mr-2">{row.kind}</span>
                    {row.label}
                  </p>
                  <p className="text-xs text-gray-400">
                    {row.kind === 'Task'
                      ? `gap score ${row.gap_score} · progress ${row.progress}%`
                      : `${row.docs_remaining} doc(s) remaining · ${row.days_left_in_phase} day(s) left`}
                    {row.expected_completion && ` · expected: ${row.expected_completion}`}
                  </p>
                </div>
                <StatusBadge status={row.flag} />
              </div>
            ))
          )}
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg">
        <h3 className="font-medium text-gray-900 px-4 py-3 border-b border-gray-100">Phase Completion</h3>
        <div className="divide-y divide-gray-100">
          {data.phase_completion.length === 0 ? (
            <p className="px-4 py-4 text-center text-gray-400 text-sm">No documents yet.</p>
          ) : (
            data.phase_completion.map((p) => (
              <div key={p.phase} className="flex items-center justify-between gap-3 px-4 py-3">
                <span className="text-sm text-gray-900">{p.phase}</span>
                <div className="flex items-center gap-3 flex-1 max-w-xs">
                  <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div className="h-full bg-indigo-500" style={{ width: `${p.percent}%` }} />
                  </div>
                  <span className="text-xs text-gray-400 w-20 text-right">
                    {p.confirmed}/{p.total} ({p.percent}%)
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        <div className="bg-white border border-gray-200 rounded-lg">
          <h3 className="font-medium text-gray-900 px-4 py-3 border-b border-gray-100">Upcoming Milestones</h3>
          <div className="divide-y divide-gray-100">
            {data.upcoming_milestones.length === 0 ? (
              <p className="px-4 py-4 text-center text-gray-400 text-sm">None upcoming.</p>
            ) : (
              data.upcoming_milestones.map((m) => (
                <div key={m.id} className="px-4 py-3 flex items-center justify-between">
                  <span className="text-sm text-gray-900">{m.name}</span>
                  <span className="text-xs text-gray-400">{m.end_date}</span>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg">
          <h3 className="font-medium text-gray-900 px-4 py-3 border-b border-gray-100">Open Issues / Incidents</h3>
          <div className="divide-y divide-gray-100">
            {Object.keys(data.open_issues_by_severity).length === 0 ? (
              <p className="px-4 py-4 text-center text-gray-400 text-sm">None open.</p>
            ) : (
              Object.entries(data.open_issues_by_severity).map(([sev, count]) => (
                <div key={sev} className="px-4 py-3 flex items-center justify-between">
                  <span className="text-sm text-gray-900">{sev}</span>
                  <span className="text-sm text-gray-500">{count}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg">
        <h3 className="font-medium text-gray-900 px-4 py-3 border-b border-gray-100">Resource Utilization</h3>
        <div className="divide-y divide-gray-100">
          {data.resource_utilization.length === 0 ? (
            <p className="px-4 py-4 text-center text-gray-400 text-sm">No resources allocated to this project.</p>
          ) : (
            data.resource_utilization.map((r) => (
              <div key={r.resource_id} className="px-4 py-3 flex items-center justify-between">
                <span className="text-sm text-gray-900">Resource #{r.resource_id}</span>
                <span className="text-xs text-gray-400">
                  {r.total_percent_this_project}% here · {r.total_percent_all_projects}% across all projects
                  {r.total_percent_all_projects > 100 && (
                    <span className="ml-2 text-red-600 font-medium">over-allocated</span>
                  )}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
