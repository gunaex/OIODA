import { useState } from "react";
import { qaApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, Empty, SignInPrompt } from "../components/ui";

const REPORTS = [
  ["execution-summary", "Execution Summary"],
  ["detailed-results", "Detailed Results"],
  ["ng-defects", "NG Defects"],
  ["evidence-completeness", "Evidence Completeness"],
  ["revision-comparison", "Revision Comparison"],
  ["cycle-comparison", "Cycle Comparison"],
  ["tester-progress", "Tester Progress"],
  ["go-live-readiness", "Go-Live Readiness"],
  ["signoff-summary", "Sign-off Summary"],
  ["storage-usage", "Storage Usage"],
];

export default function QaReportsPage() {
  const { qa, qaAuthed } = useProjectCtx();
  const slug = qa && qa.length ? qa[0].slug : null;
  const [result, setResult] = useState(null);
  const [name, setName] = useState(null);
  const [error, setError] = useState(null);

  async function open(id, label) {
    setName(label); setError(null);
    try { setResult(await qaApi.reports(slug, id)); }
    catch (e) { setError(e.message || String(e)); setResult(null); }
  }

  if (!qaAuthed) return <SignInPrompt service="QA Again" children="Sign in to view QA reports." />;
  if (!slug) return <Empty title="QA Again is not linked" />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold">Reports</h1>
        <p className="text-sm text-gray-500">QA Again reports and exports. OIDA triggers and displays; QA Again generates.</p>
      </div>

      <Card>
        <CardHeader title="Available reports" />
        <div className="flex flex-wrap gap-2 px-4 py-3">
          {REPORTS.map(([id, label]) => (
            <button key={id} onClick={() => open(id, label)} className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50">{label}</button>
          ))}
        </div>
      </Card>

      {error && <Card className="px-4 py-3 text-sm text-rose-600">{error}</Card>}

      {result && (
        <Card>
          <CardHeader title={name || "report"} />
          <pre className="max-h-96 overflow-auto whitespace-pre-wrap px-4 py-3 text-xs text-gray-700">{JSON.stringify(result, null, 2)}</pre>
        </Card>
      )}
    </div>
  );
}
