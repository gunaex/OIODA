export function SkeletonBar({ className = '' }) {
  return <div className={`animate-pulse bg-gray-200 rounded ${className}`} />;
}

export function CardSkeleton({ count = 3 }) {
  return (
    <div className="page-shell py-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        {Array.from({ length: count }).map((_, i) => (
          <div key={i} className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
            <SkeletonBar className="h-5 w-3/4" />
            <SkeletonBar className="h-4 w-full" />
            <SkeletonBar className="h-4 w-1/2" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function TableSkeleton({ rows = 5, cols = 4 }) {
  return (
    <div className="page-shell py-6 space-y-4">
      <SkeletonBar className="h-8 w-48" />
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-gray-100 flex gap-8">
          {Array.from({ length: cols }).map((_, i) => (
            <SkeletonBar key={i} className="h-4 w-24" />
          ))}
        </div>
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="p-4 border-b border-gray-50 flex gap-8">
            {Array.from({ length: cols }).map((_, j) => (
              <SkeletonBar key={j} className="h-4 w-28" />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <div className="page-shell py-6 space-y-6">
      <SkeletonBar className="h-8 w-64" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
            <SkeletonBar className="h-4 w-20" />
            <SkeletonBar className="h-8 w-16" />
            <SkeletonBar className="h-3 w-full" />
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
          <SkeletonBar className="h-5 w-32" />
          <SkeletonBar className="h-48 w-full" />
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
          <SkeletonBar className="h-5 w-32" />
          <SkeletonBar className="h-48 w-full" />
        </div>
      </div>
    </div>
  );
}

export function DetailSkeleton() {
  return (
    <div className="page-shell py-6 space-y-6">
      <div className="flex items-center gap-4">
        <SkeletonBar className="h-10 w-10 rounded-xl" />
        <SkeletonBar className="h-7 w-56" />
      </div>
      <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-4">
        <SkeletonBar className="h-4 w-full" />
        <SkeletonBar className="h-4 w-5/6" />
        <SkeletonBar className="h-4 w-3/4" />
      </div>
      <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-4">
        <SkeletonBar className="h-4 w-full" />
        <SkeletonBar className="h-4 w-2/3" />
      </div>
    </div>
  );
}
