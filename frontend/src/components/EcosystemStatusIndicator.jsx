import { useEffect, useState } from 'react'
import { getEcosystemConnectionStatus } from '../api/client'

// Real API-backed (PM-E7) — polls PM Again's own backend, which itself
// probes Account Again / Conductor Main. Never hardcodes "connected".
const Dot = ({ ok }) => (
  <span
    className={`inline-block w-2 h-2 rounded-full ${ok ? 'bg-green-500' : 'bg-gray-300'}`}
    title={ok ? 'Reachable' : 'Not reachable'}
  />
)

export default function EcosystemStatusIndicator() {
  const [status, setStatus] = useState(null)

  useEffect(() => {
    let cancelled = false
    getEcosystemConnectionStatus()
      .then((s) => {
        if (!cancelled) setStatus(s)
      })
      .catch(() => {
        if (!cancelled) setStatus(null)
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (!status) return null

  return (
    <div className="flex items-center gap-3 text-xs text-gray-500">
      <span className="flex items-center gap-1">
        <Dot ok={status.accountAgain?.reachable} /> Account Again
      </span>
      <span className="flex items-center gap-1">
        <Dot ok={status.conductorMain?.reachable} /> Conductor
      </span>
    </div>
  )
}
