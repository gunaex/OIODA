const STYLES = {
  // Suites
  ACTIVE: 'bg-green-100 text-green-700',
  ARCHIVED: 'bg-gray-100 text-gray-600',
  // Revisions
  DRAFT: 'bg-gray-100 text-gray-600',
  PUBLISHED: 'bg-green-100 text-green-700',
  SUPERSEDED: 'bg-yellow-100 text-yellow-700',
  // Test results
  PASS: 'bg-green-100 text-green-700',
  FAIL: 'bg-red-100 text-red-700',
  BLOCKED: 'bg-red-100 text-red-700',
  NOT_RUN: 'bg-gray-100 text-gray-600',
  NOT_APPLICABLE: 'bg-yellow-100 text-yellow-700',
  // Cycles
  READY: 'bg-blue-100 text-blue-700',
  IN_PROGRESS: 'bg-blue-100 text-blue-700',
  REVIEW: 'bg-yellow-100 text-yellow-700',
  COMPLETED: 'bg-green-100 text-green-700',
  LOCKED: 'bg-gray-200 text-gray-700',
  CANCELLED: 'bg-red-100 text-red-700',
  // Review status
  UNREVIEWED: 'bg-gray-100 text-gray-600',
  ACCEPTED: 'bg-green-100 text-green-700',
  CHANGES_REQUESTED: 'bg-red-100 text-red-700',
}

export default function StatusBadge({ status }) {
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs ${STYLES[status] || 'bg-gray-100 text-gray-600'}`}>
      {status}
    </span>
  )
}
