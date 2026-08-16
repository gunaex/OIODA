import { useState } from "react";
import { pmApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, Loading, Empty, SignInPrompt, Table, Tr, Td } from "../components/ui";

const REPORTS = [
  { id: "daily", label: "Daily" },
  { id: "weekly", label: "Weekly" },
  { id: "monthly", label: "Monthly" },
  { id: "phase-closure", label: "Phase Closure" },
];

export default function PmReportsPage() {
  const { pm, pmAuthed } = useProjectCtx();
  const [result, setResult] = useState(null);
  const [name, setName] = useState(null);
  const [error, setError] = useState(null);

  async function open(id) {
    setName(id); setError(null);
    try { setResult(await pmApi.pmReport(pm.slug, id)); }
    catch (e) { setError(e.message || String(e)); setResult(null); }
  }

  if (!pmAuthed) return <SignInPrompt service="PM Again" children="Sign in to view PM reports." />;
  if (!pm) return <Empty title="PM Again is not linked" />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold">Reports</h1>
        <p className="text-sm text-gray-500">PM Again report generation. OIDA triggers and displays; PM Again generates.</p>
      </div>

      <Card>
        <CardHeader title="Available reports" />
        <div className="flex flex-wrap gap-2 px-4 py-3">
          {REPORTS.map((r) => (
            <button key={r.id} onClick={() => open(r.id)} className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50">
              {r.label}
            </button>
          ))}
        </div>
      </Card>

      {error && <Card className="px-4 py-3 text-sm text-rose-600">{error}</Card>}

      {result && (
        <Card>
          <CardHeader title={`${name || ""} report`} />
          <pre className="max-h-96 overflow-auto whitespace-pre-wrap px-4 py-3 text-xs text-gray-700">{JSON.stringify(result, null, 2)}</pre>
        </Card>
      )}
    </div>
  );
}
