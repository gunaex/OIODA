import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { listHolidays, createHoliday, updateHoliday, deleteHoliday } from '../api/client'
import { useAuth } from '../auth/AuthContext.jsx'
import UserBadge from '../components/UserBadge.jsx'

const emptyForm = { holiday_date: '', name_th: '', name_en: '', is_special: false }

export default function HolidaysAdmin() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'pmo_admin'
  const [year, setYear] = useState(new Date().getFullYear())
  const [holidays, setHolidays] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState(emptyForm)

  const load = () => {
    setLoading(true)
    setLoadError(null)
    listHolidays(year)
      .then(setHolidays)
      .catch(() => setLoadError('Could not load holidays — the backend may be unreachable.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [year])

  const startEdit = (h) => {
    setEditingId(h.id)
    setAdding(false)
    setForm({ ...emptyForm, ...h, name_en: h.name_en || '' })
  }

  const startAdd = () => {
    setAdding(true)
    setEditingId(null)
    setForm({ ...emptyForm, holiday_date: `${year}-01-01` })
  }

  const cancel = () => {
    setAdding(false)
    setEditingId(null)
    setForm(emptyForm)
  }

  const save = async () => {
    if (!form.holiday_date || !form.name_th.trim()) return
    const payload = {
      holiday_date: form.holiday_date,
      name_th: form.name_th,
      name_en: form.name_en || null,
      is_special: form.is_special,
    }
    if (adding) {
      await createHoliday(payload)
    } else {
      await updateHoliday(editingId, payload)
    }
    cancel()
    load()
  }

  const remove = async (id) => {
    if (!confirm('Delete this holiday? Business-day calculations (SLA due dates, slippage) will treat that date as a working day from now on.')) return
    await deleteHoliday(id)
    load()
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-10">
        <div className="flex items-center justify-between mb-6 gap-4">
          <div className="flex items-center gap-4">
            <NavLink to="/" className="text-sm text-gray-500 hover:text-gray-800">
              &larr; Dashboard
            </NavLink>
            <h1 className="text-2xl font-semibold text-gray-900">Thai Holidays</h1>
          </div>
          <UserBadge />
        </div>

        <p className="text-sm text-gray-500 mb-6">
          Used by SLA due dates and the Slippage Predictor to skip weekends and Thai public holidays instead of
          counting calendar days.
          {!isAdmin && ' Only pmo_admin can add or edit entries — you have read-only access.'}
        </p>

        <div className="bg-white border border-gray-200 rounded-lg">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-500">Year</label>
              <input
                type="number"
                value={year}
                onChange={(e) => setYear(Number(e.target.value))}
                className="w-24 px-2 py-1 border border-gray-300 rounded-md text-sm"
              />
            </div>
            {isAdmin && !adding && editingId === null && (
              <button
                onClick={startAdd}
                className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
              >
                + Add Holiday
              </button>
            )}
          </div>

          {isAdmin && (adding || editingId !== null) && (
            <div className="flex flex-wrap gap-2 px-4 py-3 border-b border-gray-100 bg-gray-50">
              <input
                type="date"
                value={form.holiday_date}
                onChange={(e) => setForm({ ...form, holiday_date: e.target.value })}
                className="px-3 py-2 border border-gray-300 rounded-md text-sm"
              />
              <input
                value={form.name_th}
                onChange={(e) => setForm({ ...form, name_th: e.target.value })}
                placeholder="ชื่อวันหยุด (Thai name)"
                className="flex-1 min-w-[160px] px-3 py-2 border border-gray-300 rounded-md text-sm"
              />
              <input
                value={form.name_en}
                onChange={(e) => setForm({ ...form, name_en: e.target.value })}
                placeholder="English name (optional)"
                className="flex-1 min-w-[160px] px-3 py-2 border border-gray-300 rounded-md text-sm"
              />
              <label className="flex items-center gap-1.5 text-sm text-gray-600 px-2">
                <input
                  type="checkbox"
                  checked={form.is_special}
                  onChange={(e) => setForm({ ...form, is_special: e.target.checked })}
                />
                Special (ad-hoc, not annual)
              </label>
              <button onClick={save} className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700">
                Save
              </button>
              <button onClick={cancel} className="px-3 py-1.5 text-sm text-gray-600 hover:underline">
                Cancel
              </button>
            </div>
          )}

          <div className="divide-y divide-gray-100">
            {loading ? (
              <p className="px-4 py-4 text-center text-gray-400 text-sm">Loading…</p>
            ) : loadError ? (
              <p className="px-4 py-4 text-center text-sm text-red-600">
                {loadError}{' '}
                <button onClick={load} className="underline font-medium">
                  Retry
                </button>
              </p>
            ) : holidays.length === 0 ? (
              <p className="px-4 py-4 text-center text-gray-400 text-sm">No holidays recorded for {year}.</p>
            ) : (
              holidays.map((h) => (
                <div key={h.id} className="flex items-center justify-between gap-3 px-4 py-3">
                  <div className="min-w-0">
                    <p className="text-sm text-gray-900">
                      {h.holiday_date} — {h.name_th}
                      {h.is_special && (
                        <span className="ml-2 px-1.5 py-0.5 text-[10px] uppercase tracking-wide rounded bg-indigo-50 text-indigo-600">
                          special
                        </span>
                      )}
                    </p>
                    {h.name_en && <p className="text-xs text-gray-400">{h.name_en}</p>}
                  </div>
                  {isAdmin && (
                    <div className="flex items-center gap-3 shrink-0">
                      <button onClick={() => startEdit(h)} className="text-sm text-indigo-600 hover:underline">
                        Edit
                      </button>
                      <button onClick={() => remove(h.id)} className="text-sm text-red-600 hover:underline">
                        Delete
                      </button>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
