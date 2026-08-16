import { useEffect, useState } from "react";
import { documentApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, Loading, Badge } from "../components/ui";
import SuggestionCard from "../components/SuggestionCard";

export default function SuggestionsPage() {
  const { project } = useProjectCtx();
  const [suggestions, setSuggestions] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  function load() {
    if (!project) return;
    documentApi.listSuggestions(project.id).then(setSuggestions).catch((e) => setError(e.message));
  }
  useEffect(load, [project?.id]);

  async function generate() {
    setBusy(true); setError(null);
    try {
      const created = await documentApi.generateSuggestions(project.id, "STANDARD");
      load();
      if (created.length === 0) setError("No new suggestions — every known concern is already captured.");
    } catch (e) { setError(e.message || String(e)); }
    finally { setBusy(false); }
  }

  if (!project) return <Loading />;

  const open = (suggestions || []).filter((s) => !["ACCEPTED", "REJECTED", "RESOLVED"].includes(s.status));
  const high = open.filter((s) => s.severity === "HIGH").length;
  const waiting = open.filter((s) => !s.answer).length;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold">OIDA Suggestions</h1>
          <p className="text-sm text-gray-500">AI observes and suggests · the human decides. Nothing is applied without review.</p>
        </div>
        <button onClick={generate} disabled={busy} className="rounded-lg bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-700 disabled:opacity-50">
          {busy ? "Consulting…" : "Consult OIDA"}
        </button>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Stat label="Open suggestions" value={open.length} />
        <Stat label="High priority" value={high} />
        <Stat label="Waiting answer" value={waiting} />
      </div>

      {error && <Card className="px-4 py-3 text-sm text-rose-600">{error}</Card>}

      {!suggestions ? <Loading /> : (
        <div className="space-y-3">
          {suggestions.length === 0 && (
            <Card className="px-6 py-10 text-center text-sm text-gray-500">No suggestions. Click “Consult OIDA” to review the project for concerns.</Card>
          )}
          {suggestions.map((s) => <SuggestionCard key={s.id} suggestion={s} onChanged={load} />)}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white px-4 py-3">
      <div className="text-2xl font-bold text-gray-900">{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  );
}
