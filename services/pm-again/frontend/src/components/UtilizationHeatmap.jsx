import { useEffect, useMemo, useState } from 'react'
import { getResourceUtilization } from '../api/client'

function mondayOf(d) {
  const date = new Date(d)
  const day = (date.getDay() + 6) % 7 // 0 = Monday
  date.setDate(date.getDate() - day)
  return date
}

function toISODate(d) {
  return d.toISOString().slice(0, 10)
}

function heatmapClass(percent) {
  if (percent > 100) return 'bg-red-100 text-red-700'
  if (percent >= 80) return 'bg-yellow-100 text-yellow-700'
  if (percent > 0) return 'bg-green-100 text-green-700'
  return 'bg-gray-50 text-gray-300'
}

export default function UtilizationHeatmap() {
  const [heatmap, setHeatmap] = useState([])
  const [from, setFrom] = useState(() => toISODate(mondayOf(new Date())))
  const [to, setTo] = useState(() => {
    const monday = mondayOf(new Date())
    monday.setDate(monday.getDate() + 27)
    return toISODate(monday)
  })
  const [error, setError] = useState(null)

  const load = () => {
    setError(null)
    getResourceUtilization(from, to)
      .then(setHeatmap)
      .catch(() => setError('Could not load the utilization heatmap.'))
  }

  useEffect(load, [from, to])

  const weeks = useMemo(() => heatmap[0]?.weeks.map((w) => w.week) || [], [heatmap])

  return (
    <div className="bg-white border border-gray-200 rounded-lg">
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-b border-gray-100">
        <h2 className="font-medium text-gray-900">Utilization Heatmap</h2>
        <div className="flex items-center gap-2 text-sm">
          <input
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
            className="px-2 py-1 border border-gray-300 rounded-md"
          />
          <span className="text-gray-400">to</span>
          <input
            type="date"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            className="px-2 py-1 border border-gray-300 rounded-md"
          />
        </div>
      </div>
      <div className="p-4 overflow-x-auto">
        {error ? (
          <p className="text-sm text-red-600">{error}</p>
        ) : heatmap.length === 0 ? (
          <p className="text-sm text-gray-400">No resources to show.</p>
        ) : (
          <table className="min-w-full text-sm">
            <thead>
              <tr>
                <th className="text-left font-medium text-gray-500 pr-4 pb-2">Resource</th>
                {weeks.map((w) => (
                  <th key={w} className="text-center font-medium text-gray-500 px-2 pb-2 whitespace-nowrap">
                    {w}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {heatmap.map((row) => (
                <tr key={row.resource_id}>
                  <td className="pr-4 py-1 text-gray-900 whitespace-nowrap">{row.resource_name}</td>
                  {row.weeks.map((w) => (
                    <td key={w.week} className="px-2 py-1 text-center">
                      <span className={`inline-block min-w-[3rem] px-2 py-1 rounded ${heatmapClass(w.total_percent)}`}>
                        {w.total_percent}%
                      </span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
