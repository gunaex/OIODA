import { useEffect, useState } from 'react'
import { getQaResult } from '../api/client'
import StatusBadge from './StatusBadge.jsx'

/**
 * QA-E8.1/E8.2/E8.3 — shown only for a cycle that actually originated
 * from a Conductor QARequest (getQaResult 404s otherwise, which is not
 * an error here — most cycles are manually created and this renders
 * nothing for them, per "no ecosystem metadata clutter on manual work").
 *
 * Authority wording is deliberate: "QA Result" / "QA Acceptance", never
 * "Final Delivery Readiness" — QA Again owns the QAResult, Conductor Main
 * owns whether the ecosystem actually ships (QA_UI_AUTHORITY_TRUTHFUL).
 */
export default function EcosystemPanel({ slug, cycleId }) {
  const [result, setResult] = useState(null)
  const [state, setState] = useState('loading') // loading | none | ready

  useEffect(() => {
    let cancelled = false
    setState('loading')
    getQaResult(slug, cycleId)
      .then((r) => {
        if (cancelled) return
        setResult(r)
        setState('ready')
      })
      .catch(() => {
        if (cancelled) return
        setState('none')
      })
    return () => {
      cancelled = true
    }
  }, [slug, cycleId])

  if (state !== 'ready' || !result) return null

  return (
    <div className="bg-indigo-50 border border-indigo-200 rounded-lg px-4 py-3 text-sm">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs font-medium text-indigo-700 uppercase tracking-wide">Source: Conductor Main</span>
        <StatusBadge status={result.qualityGate} />
        <span className="text-xs text-indigo-400">
          {result.testSummary?.passed ?? 0}/{result.testSummary?.total ?? 0} passed
        </span>
      </div>
      <dl className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 text-xs text-indigo-800">
        <div className="flex gap-1">
          <dt className="text-indigo-500">QARequest:</dt>
          <dd className="font-mono">{result.qaRequestId}</dd>
        </div>
        <div className="flex gap-1">
          <dt className="text-indigo-500">Correlation:</dt>
          <dd className="font-mono">{result.correlationId}</dd>
        </div>
      </dl>
      <p className="mt-2 text-[11px] text-indigo-400">
        This is QA Again's own QA Result for this cycle — final delivery readiness across the whole ecosystem is
        decided separately by Conductor Main, not by QA Again.
      </p>
    </div>
  )
}
