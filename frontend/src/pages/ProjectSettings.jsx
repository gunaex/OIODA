import { useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { getEffortConfig, updateEffortConfig } from '../api/client'
import { useAuth } from '../auth/AuthContext.jsx'

// Project Settings → Effort & Budget. This is the page the Budget Gauge and
// the CR impact panel link to when they say "needs
// effort_estimate_config.contracted_total_md" — the number existed only as an
// API field before, with nowhere to type it.

const NUMERIC_FIELDS = [
  'contracted_total_md',
  'rate_thb_per_md',
  'productivity_screen',
  'productivity_batch',
  'productivity_report',
  'working_days_per_month',
  'phase_ratio_dr',
  'phase_ratio_dnpu',
  'phase_ratio_iftbct',
  'hil_price_discount_percent',
]
const BOOLEAN_FIELDS = ['show_delivery_mode_in_client_docs', 'hil_restricted']

const RATIO_FIELDS = ['phase_ratio_dr', 'phase_ratio_dnpu', 'phase_ratio_iftbct']
const RATIO_TOLERANCE = 1e-6

export default function ProjectSettings() {
  const { slug } = useParams()
  const [searchParams] = useSearchParams()
  const { user } = useAuth()
  const isPmoAdmin = user?.role === 'pmo_admin'
  // Deep-linked from "needs …" so the field that's missing is obvious on arrival.
  const highlight = searchParams.get('field')

  const [form, setForm] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true)
    getEffortConfig(slug)
      .then((cfg) =>
        setForm(
          Object.fromEntries(
            Object.entries(cfg).map(([k, v]) => [k, v == null ? '' : typeof v === 'boolean' ? v : String(v)]),
          ),
        ),
      )
      .catch(() => setError('Could not load the project settings.'))
      .finally(() => setLoading(false))
  }, [slug])

  const set = (key) => (e) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setForm((f) => ({ ...f, [key]: value }))
    setSaved(false)
  }

  const ratioSum = form ? RATIO_FIELDS.reduce((sum, k) => sum + (Number(form[k]) || 0), 0) : 0
  const ratioValid = Math.abs(ratioSum - 1) < RATIO_TOLERANCE

  const save = async () => {
    if (!ratioValid) {
      setError(`Phase ratios must add up to 1.0 — they currently total ${ratioSum.toFixed(4)}.`)
      return
    }
    setSaving(true)
    setError(null)
    try {
      const payload = {}
      for (const key of NUMERIC_FIELDS) {
        payload[key] = form[key] === '' ? null : Number(form[key])
      }
      for (const key of BOOLEAN_FIELDS) {
        payload[key] = Boolean(form[key])
      }
      const updated = await updateEffortConfig(slug, payload)
      setForm(
        Object.fromEntries(
          Object.entries(updated).map(([k, v]) => [k, v == null ? '' : typeof v === 'boolean' ? v : String(v)]),
        ),
      )
      setSaved(true)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not save the settings.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <p className="text-sm text-gray-400">Loading…</p>
  if (!form) return <p className="text-sm text-red-600">{error || 'Settings unavailable.'}</p>

  if (!isPmoAdmin) {
    return (
      <div className="reading-col">
        <h2 className="text-lg font-semibold text-gray-900 mb-2">Effort &amp; Budget</h2>
        <p className="text-sm text-gray-500">
          Only a PMO admin can change these settings. The contracted man-days and the productivity figures drive
          every effort number in the project, so they're deliberately locked down.
        </p>
      </div>
    )
  }

  return (
    <div className="max-w-3xl">
      <h2 className="text-lg font-semibold text-gray-900">Project Settings — Effort &amp; Budget</h2>
      <p className="text-xs text-gray-500 mb-5">
        These feed the Function Point model and the Effort Budget Gauge. Defaults come from the customer's own
        estimating spreadsheet; change them only when this project actually negotiated something different.
      </p>

      {error && <p className="text-sm text-red-600 mb-3">{error}</p>}

      <Card
        title="Contract"
        subtitle="Without contracted man-days there is no budget to measure against, so the gauge stays blank."
      >
        <Field
          label="Contracted total (MD)"
          hint="Man-days sold. This is the one field the Budget Gauge cannot work without."
          highlight={highlight === 'contracted_total_md'}
        >
          <input
            type="number"
            step="0.1"
            min="0"
            value={form.contracted_total_md}
            onChange={set('contracted_total_md')}
            placeholder="e.g. 450"
            className="w-32 border border-gray-300 rounded px-2 py-1 text-sm"
          />
        </Field>
        <Field label="Day rate (THB / MD)" hint="Used for CR cost when a function carries no price of its own.">
          <input
            type="number"
            step="100"
            min="0"
            value={form.rate_thb_per_md}
            onChange={set('rate_thb_per_md')}
            placeholder="e.g. 7500"
            className="w-32 border border-gray-300 rounded px-2 py-1 text-sm"
          />
        </Field>
      </Card>

      <Card title="Productivity" subtitle="Function points delivered per man-month, by work type.">
        <div className="flex flex-wrap gap-4">
          <Small label="Screen" defaultHint="4.2">
            <input type="number" step="0.1" min="0.1" value={form.productivity_screen} onChange={set('productivity_screen')} className="w-20 border border-gray-300 rounded px-2 py-1 text-sm" />
          </Small>
          <Small label="Batch" defaultHint="4.6">
            <input type="number" step="0.1" min="0.1" value={form.productivity_batch} onChange={set('productivity_batch')} className="w-20 border border-gray-300 rounded px-2 py-1 text-sm" />
          </Small>
          <Small label="Report" defaultHint="4.6">
            <input type="number" step="0.1" min="0.1" value={form.productivity_report} onChange={set('productivity_report')} className="w-20 border border-gray-300 rounded px-2 py-1 text-sm" />
          </Small>
          <Small label="Working days / month" defaultHint="20">
            <input type="number" step="0.5" min="1" value={form.working_days_per_month} onChange={set('working_days_per_month')} className="w-20 border border-gray-300 rounded px-2 py-1 text-sm" />
          </Small>
        </div>
      </Card>

      <Card title="Phase split" subtitle="How a man-month is divided across the delivery phases. Must total 1.0.">
        <div className="flex flex-wrap items-end gap-4">
          <Small label="DR" defaultHint="0.30">
            <input type="number" step="0.01" min="0" max="1" value={form.phase_ratio_dr} onChange={set('phase_ratio_dr')} className="w-20 border border-gray-300 rounded px-2 py-1 text-sm" />
          </Small>
          <Small label="DN&PU" defaultHint="0.40">
            <input type="number" step="0.01" min="0" max="1" value={form.phase_ratio_dnpu} onChange={set('phase_ratio_dnpu')} className="w-20 border border-gray-300 rounded px-2 py-1 text-sm" />
          </Small>
          <Small label="IFT/BCT" defaultHint="0.30">
            <input type="number" step="0.01" min="0" max="1" value={form.phase_ratio_iftbct} onChange={set('phase_ratio_iftbct')} className="w-20 border border-gray-300 rounded px-2 py-1 text-sm" />
          </Small>
          <span className={`text-sm ${ratioValid ? 'text-gray-500' : 'text-red-600 font-medium'}`}>
            total {ratioSum.toFixed(2)}
            {!ratioValid && ' — must be 1.00'}
          </span>
        </div>
      </Card>

      <Card
        title="Delivery mode"
        subtitle="HUMAN-in-LOOP estimates assume tooling assists parts of the work. Effort reduction and price discount are set separately on purpose."
      >
        <Field
          label="Price discount for HUMAN-in-LOOP (%)"
          hint="A commercial decision, not a consequence of the effort reduction. Whatever effort drops by, this is what you choose to pass on."
        >
          <input
            type="number"
            step="1"
            min="0"
            max="100"
            value={form.hil_price_discount_percent}
            onChange={set('hil_price_discount_percent')}
            className="w-24 border border-gray-300 rounded px-2 py-1 text-sm"
          />
        </Field>
        <Field
          label="Show delivery mode in client documents"
          hint="Off by default: exported documents show only the final man-days and price, with no mention of how the work is produced."
        >
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={Boolean(form.show_delivery_mode_in_client_docs)}
              onChange={set('show_delivery_mode_in_client_docs')}
            />
            Include delivery mode and leverage breakdown in exports
          </label>
        </Field>
        <Field
          label="Restrict HUMAN-in-LOOP on this project"
          hint="For contracts with clauses about how data may be processed — hospitals, government, anything with a data-handling restriction. Turning this on disables the toggle everywhere and makes the backend refuse it."
        >
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input type="checkbox" checked={Boolean(form.hil_restricted)} onChange={set('hil_restricted')} />
            This contract does not permit HUMAN-in-LOOP delivery
          </label>
        </Field>
      </Card>

      <div className="flex items-center gap-3">
        <button
          onClick={save}
          disabled={saving || !ratioValid}
          className="px-4 py-2 text-sm bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
        >
          {saving ? 'Saving…' : saved ? 'Saved' : 'Save settings'}
        </button>
        {saved && <span className="text-sm text-green-600">Settings saved.</span>}
      </div>
    </div>
  )
}

function Card({ title, subtitle, children }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5 mb-4">
      <h3 className="text-sm font-semibold text-gray-800">{title}</h3>
      {subtitle && <p className="text-xs text-gray-500 mb-3">{subtitle}</p>}
      <div className="space-y-3">{children}</div>
    </div>
  )
}

function Field({ label, hint, highlight, children }) {
  return (
    <div className={highlight ? 'ring-2 ring-indigo-400 rounded-md p-2 -m-2 bg-indigo-50/40' : ''}>
      <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
      {children}
      {hint && <p className="text-[11px] text-gray-400 mt-1 reading-col">{hint}</p>}
    </div>
  )
}

function Small({ label, defaultHint, children }) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1">
        {label} <span className="text-gray-300">({defaultHint})</span>
      </label>
      {children}
    </div>
  )
}
