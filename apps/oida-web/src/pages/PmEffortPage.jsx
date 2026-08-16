import { useEffect, useState } from "react";
import { pmApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, Loading, Empty, Badge } from "../components/ui";

export default function PmEffortPage() {
  const { pm } = useProjectCtx();
  const [summary, setSummary] = useState(null);
  const [budget, setBudget] = useState(null);

  useEffect(() => {
    if (!pm?.slug) return;
    pmApi.effortSummary(pm.slug).then(setSummary).catch(() => setSummary(null));
    pmApi.effortBudget(pm.slug).then(setBudget).catch(() => setBudget(null));
  }, [pm?.slug]);

  if (!pm) return <Empty title="PM Again is not linked" />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold">Effort</h1>
        <p className="text-sm text-gray-500">Function-point effort estimates. Authority: PM Again (read-only in OIDA).</p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Total MD" value={summary?.total_man_days ?? "—"} />
        <Stat label="Estimate count" value={summary?.estimate_count ?? "—"} />
        <Stat label="Budget (MD)" value={budget?.total_md ?? budget?.contracted_total_md ?? "—"} />
        <Stat label="Rate (THB/MD)" value={budget?.rate_thb_per_md ?? "—"} />
      </div>

      {summary && summary.by_function && (
        <Card>
          <CardHeader title="By workstream" />
          <div className="space-y-1 px-4 py-3">
            {summary.by_function.map((f, i) => (
              <div key={i} className="flex justify-between text-sm text-gray-700">
                <span>{f.name || f.function_name || f.code}</span>
                <span>{f.man_days ?? f.total_md ?? "—"} MD</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card>
        <CardHeader title="Estimation status" />
        <div className="px-4 py-3 text-sm text-gray-600">
          {budget ? "Effort budget configured." : "No effort budget recorded yet."} Estimates remain PM Again authority; OIDA reads, never writes.
        </div>
      </Card>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white px-4 py-3">
      <div className="text-xl font-bold text-gray-900">{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  );
}
