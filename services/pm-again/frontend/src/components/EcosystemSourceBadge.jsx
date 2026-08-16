import { useEffect, useState } from 'react'
import { getEcosystemSource } from '../api/client'

// Additive, real-API-backed (PM-E7): renders nothing for a normal
// manually-created project. Only shows up when this project actually has
// an ExternalWorkReference (e.g. it was created by a Conductor Main
// DeliveryWorkPackage) — never fabricated, never shown for local-only work.
export default function EcosystemSourceBadge({ slug }) {
  const [source, setSource] = useState(null)

  useEffect(() => {
    let cancelled = false
    getEcosystemSource(slug)
      .then((s) => {
        if (!cancelled) setSource(s)
      })
      .catch(() => {
        if (!cancelled) setSource(null)
      })
    return () => {
      cancelled = true
    }
  }, [slug])

  if (!source) return null

  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-2 text-xs text-blue-900 flex flex-wrap gap-x-6 gap-y-1">
      <span>
        <span className="font-medium">Source:</span> {source.sourceSystem}
      </span>
      <span>
        <span className="font-medium">{source.sourceObjectType}:</span> {source.sourceObjectId}
      </span>
      <span>
        <span className="font-medium">Correlation ID:</span> {source.correlationId}
      </span>
      <span>
        <span className="font-medium">Ecosystem status:</span> {source.status}
      </span>
    </div>
  )
}
