import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  listCycles,
  listSuites,
  listRevisions,
  getExecutionSummary,
  getDetailedResults,
  getNgDefects,
  getEvidenceCompletenessReport,
  getRevisionComparison,
  getCycleComparison,
  getTesterProgress,
  getGoLiveReadinessReport,
  getSignoffSummary,
  getStorageUsageReport,
  exportExcelUrl,
  exportZipUrl,
} from '../api/client'

// One consolidated Reports page instead of 10 separate screens — see
// docs/ROADMAP.md Phase 6 for why (the spec names 10 reports; all 10
// exist as real backend endpoints, but a dedicated page per report is
// disproportionate for this MVP and duplicates the Excel export).
const REPORT_TYPES = [
  { value: 'execution-summary', label: 'Execution Summary' },
  { value: 'detailed-results', label: 'Detailed Test Results' },
  { value: 'ng-defects', label: 'NG and Defect Report' },
  { value: 'evidence-completeness', label: 'Evidence Completeness' },
  { value: 'revision-comparison', label: 'Revision Comparison' },
  { value: 'cycle-comparison', label: 'Cycle-to-Cycle Comparison' },
  { value: 'tester-progress', label: 'Tester Progress' },
  { value: 'go-live-readiness', label: 'Go-Live Readiness' },
  { value: 'signoff-summary', label: 'Audit/Sign-off Summary' },
  { value: 'storage-usage', label: 'Project Storage Usage' },
]

function GenericTable({ rows }) {
  if (!rows || rows.length === 0) return <p className="text-xs text-gray-400">No rows.</p>
  const columns = Object.keys(rows[0])
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-gray-100 text-left text-gray-500 uppercase">
            {columns.map((c) => (
              <th key={c} className="px-3 py-2 whitespace-nowrap">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-gray-50">
              {columns.map((c) => (
                <td key={c} className="px-3 py-2 whitespace-nowrap max-w-xs truncate">
                  {typeof row[c] === 'boolean' ? String(row[c]) : row[c] ?? '—'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function ReportsPage() {
  const { slug } = useParams()
  const [cycles, setCycles] = useState([])
  const [cycleId, setCycleId] = useState('')
  const [reportType, setReportType] = useState('execution-summary')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Only used by the two comparison report types.
  const [suites, setSuites] = useState([])
  const [suiteId, setSuiteId] = useState('')
  const [revisions, setRevisions] = useState([])
  const [revisionAId, setRevisionAId] = useState('')
  const [revisionBId, setRevisionBId] = useState('')
  const [cycleBId, setCycleBId] = useState('')

  useEffect(() => {
    listCycles(slug).then((c) => {
      setCycles(c)
      if (c.length > 0) setCycleId(String(c[0].id))
    })
    listSuites(slug).then(setSuites)
  }, [slug])

  useEffect(() => {
    if (suiteId) listRevisions(slug, suiteId).then(setRevisions)
  }, [slug, suiteId])

  const load = async () => {
    setLoading(true)
    setError(null)
    setData(null)
    try {
      let result
      switch (reportType) {
        case 'execution-summary':
          result = await getExecutionSummary(slug, cycleId)
          break
        case 'detailed-results':
          result = await getDetailedResults(slug, cycleId)
          break
        case 'ng-defects':
          result = await getNgDefects(slug, cycleId)
          break
        case 'evidence-completeness':
          result = await getEvidenceCompletenessReport(slug, cycleId)
          break
        case 'revision-comparison':
          result = await getRevisionComparison(slug, revisionAId, revisionBId)
          break
        case 'cycle-comparison':
          result = await getCycleComparison(slug, cycleId, cycleBId)
          break
        case 'tester-progress':
          result = await getTesterProgress(slug, cycleId)
          break
        case 'go-live-readiness':
          result = await getGoLiveReadinessReport(slug, cycleId)
          break
        case 'signoff-summary':
          result = await getSignoffSummary(slug, cycleId)
          break
        case 'storage-usage':
          result = await getStorageUsageReport(slug)
          break
        default:
          result = null
      }
      setData(result)
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not load this report')
    } finally {
      setLoading(false)
    }
  }

  const needsRevisionPicker = reportType === 'revision-comparison'
  const needsSecondCycle = reportType === 'cycle-comparison'
  const needsCycle = reportType !== 'storage-usage' && !needsRevisionPicker

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-xl font-semibold text-gray-900">Reports</h2>
        {cycleId && (
          <div className="flex gap-2">
            <a href={exportExcelUrl(slug, cycleId)} className="px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-50">
              Export Excel
            </a>
            <a href={exportZipUrl(slug, cycleId)} className="px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-50">
              Export ZIP Package
            </a>
          </div>
        )}
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-5 flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Report</label>
          <select
            value={reportType}
            onChange={(e) => setReportType(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
          >
            {REPORT_TYPES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </div>

        {needsCycle && (
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Cycle{needsSecondCycle ? ' A' : ''}</label>
            <select
              value={cycleId}
              onChange={(e) => setCycleId(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              {cycles.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        )}
        {needsSecondCycle && (
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Cycle B</label>
            <select
              value={cycleBId}
              onChange={(e) => setCycleBId(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            >
              <option value="">Select…</option>
              {cycles.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        )}
        {needsRevisionPicker && (
          <>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Suite</label>
              <select
                value={suiteId}
                onChange={(e) => setSuiteId(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
              >
                <option value="">Select…</option>
                {suites.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Revision A</label>
              <select
                value={revisionAId}
                onChange={(e) => setRevisionAId(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
              >
                <option value="">Select…</option>
                {revisions.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.revision_label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Revision B</label>
              <select
                value={revisionBId}
                onChange={(e) => setRevisionBId(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
              >
                <option value="">Select…</option>
                {revisions.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.revision_label}
                  </option>
                ))}
              </select>
            </div>
          </>
        )}

        <button onClick={load} className="px-4 py-2 bg-emerald-600 text-white text-sm font-medium rounded-md hover:bg-emerald-700">
          Run Report
        </button>
      </div>

      {loading && <p className="text-sm text-gray-500">Loading…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {data && (
        <div className="bg-white border border-gray-200 rounded-lg p-5">
          {Array.isArray(data) ? (
            <GenericTable rows={data} />
          ) : reportType === 'ng-defects' ? (
            <div className="space-y-4">
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase mb-1">NG Cases</p>
                <GenericTable rows={data.ng_cases} />
              </div>
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase mb-1">Defects</p>
                <GenericTable rows={data.defects} />
              </div>
            </div>
          ) : (
            <pre className="text-xs text-gray-700 whitespace-pre-wrap">{JSON.stringify(data, null, 2)}</pre>
          )}
        </div>
      )}
    </div>
  )
}
