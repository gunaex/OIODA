const STATUS_STYLES = {
  draft: 'bg-gray-100 text-gray-700 border-gray-200',
  active: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  clarifying: 'bg-blue-50 text-blue-700 border-blue-200',
  approved: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  change_proposed: 'bg-amber-50 text-amber-700 border-amber-200',
  superseded: 'bg-purple-50 text-purple-700 border-purple-200',
  archived: 'bg-gray-100 text-gray-500 border-gray-200',
  deleted: 'bg-red-50 text-red-500 border-red-200',
  available: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  offline: 'bg-gray-100 text-gray-500 border-gray-200',
  rate_limited: 'bg-amber-50 text-amber-700 border-amber-200',
  suspended: 'bg-red-50 text-red-700 border-red-200',
};

export default function StatusBadge({ status, className = '' }) {
  const style = STATUS_STYLES[status] || STATUS_STYLES.draft;
  const label = status.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${style} ${className}`}
    >
      {label}
    </span>
  );
}
