import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { reportUrl } from '../api/client'

const PHASES = [
  { code: 10, name: 'UR' },
  { code: 20, name: 'DR' },
  { code: 30, name: 'DN' },
  { code: 40, name: 'PU' },
  { code: 50, name: 'ST' },
  { code: 60, name: 'UT' },
  { code: 70, name: 'TR' },
  { code: 80, name: 'IP' },
  { code: 90, name: 'MA' },
]

const todayISO = () => new Date().toISOString().slice(0, 10)
const mondayOfThisWeekISO = () => {
  const d = new Date()
  const day = (d.getDay() + 6) % 7 // 0 = Monday
  d.setDate(d.getDate() - day)
  return d.toISOString().slice(0, 10)
}
const thisMonthYYYYMM = () => new Date().toISOString().slice(0, 7)

export default function ReportsPage() {
  const { slug } = useParams()
  const [dailyDate, setDailyDate] = useState(todayISO())
  const [weekStart, setWeekStart] = useState(mondayOfThisWeekISO())
  const [month, setMonth] = useState(thisMonthYYYYMM())
  const [phaseCode, setPhaseCode] = useState(PHASES[0].code)

  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-900 mb-1">Reports</h2>
      <p className="text-sm text-gray-500 mb-6">
        Generate an Excel report from the data already in the system — no manual compiling.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <ReportCard title="Daily Report" description="Task status updates + notes created on a given day.">
          <input
            type="date"
            value={dailyDate}
            onChange={(e) => setDailyDate(e.target.value)}
            className="border border-gray-300 rounded px-2 py-1.5 text-sm"
          />
          <a
            href={reportUrl(slug, 'daily', { date: dailyDate })}
            className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
          >
            Generate
          </a>
        </ReportCard>

        <ReportCard title="Weekly Report" description="Progress summary by phase + status changes over 7 days.">
          <input
            type="date"
            value={weekStart}
            onChange={(e) => setWeekStart(e.target.value)}
            className="border border-gray-300 rounded px-2 py-1.5 text-sm"
          />
          <a
            href={reportUrl(slug, 'weekly', { week_start: weekStart })}
            className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
          >
            Generate
          </a>
        </ReportCard>

        <ReportCard title="Monthly Report" description="Executive summary, phase breakdown, overdue tasks & pending mandatory docs.">
          <input
            type="month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            className="border border-gray-300 rounded px-2 py-1.5 text-sm"
          />
          <a
            href={reportUrl(slug, 'monthly', { month })}
            className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
          >
            Generate
          </a>
        </ReportCard>

        <ReportCard title="Phase Closure Report" description="Document checklist (M/O) + sign-off history for one phase.">
          <select
            value={phaseCode}
            onChange={(e) => setPhaseCode(Number(e.target.value))}
            className="border border-gray-300 rounded px-2 py-1.5 text-sm"
          >
            {PHASES.map((p) => (
              <option key={p.code} value={p.code}>
                {p.name} ({p.code})
              </option>
            ))}
          </select>
          <a
            href={reportUrl(slug, 'phase-closure', { phase_code: phaseCode })}
            className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
          >
            Generate
          </a>
        </ReportCard>
      </div>
    </div>
  )
}

function ReportCard({ title, description, children }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5">
      <h3 className="font-medium text-gray-900 mb-1">{title}</h3>
      <p className="text-sm text-gray-500 mb-4">{description}</p>
      <div className="flex flex-wrap items-center gap-3">{children}</div>
    </div>
  )
}
