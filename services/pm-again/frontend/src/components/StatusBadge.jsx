const STYLES = {
  // Functions / generic
  Draft: 'bg-gray-100 text-gray-600',
  Confirmed: 'bg-green-100 text-green-700',
  InProgress: 'bg-blue-100 text-blue-700',
  Done: 'bg-green-100 text-green-700',
  // Tasks
  Todo: 'bg-gray-100 text-gray-600',
  Blocked: 'bg-red-100 text-red-700',
  // Documents
  InReview: 'bg-yellow-100 text-yellow-700',
  Rejected: 'bg-red-100 text-red-700',
  // RAG / Slippage
  green: 'bg-green-100 text-green-700',
  amber: 'bg-yellow-100 text-yellow-700',
  red: 'bg-red-100 text-red-700',
  on_track: 'bg-green-100 text-green-700',
  at_risk: 'bg-yellow-100 text-yellow-700',
  overdue: 'bg-red-100 text-red-700',
}

export default function StatusBadge({ status }) {
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs ${STYLES[status] || 'bg-gray-100 text-gray-600'}`}>
      {status}
    </span>
  )
}
