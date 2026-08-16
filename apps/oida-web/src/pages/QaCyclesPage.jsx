import { useEffect, useState } from "react";
import { qaApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, StatusBadge, Loading, Empty, SignInPrompt, Table, Tr, Td } from "../components/ui";

const RESULT_STATUSES = ["NOT_RUN", "PASS", "FAIL", "BLOCKED", "NOT_APPLICABLE"];

export default function QaCyclesPage() {
  const { qa, qaAuthed } = useProjectCtx();
  const slug = qa && qa.length ? qa[0].slug : null;
  const [cycles, setCycles] = useState(null);
  const [results, setResults] = useState(null);
  const [cycleId, setCycleId] = useState(null);
  const [cycleForm, setCycleForm] = useState({ name: "", environment: "UAT", revision_id: "" });
  const [revisionOptions, setRevisionOptions] = useState([]);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  function load() { if (slug) qaApi.cycles(slug).then(setCycles).catch(() => setCycles([])); }
  useEffect(load, [slug]);

  // Published revisions are the only valid target for a new cycle.
  useEffect(() => {
    if (!slug) return;
    (async () => {
      try {
        const suites = await qaApi.suites(slug);
        const opts = [];
        for (const s of suites) {
          const revs = await qaApi.revisions(slug, s.id).catch(() => []);
          for (const r of revs) {
            if (r.status === "PUBLISHED") opts.push({ id: r.id, suite_id: s.id, label: `${s.name} · ${r.revision_label}` });
          }
        }
        setRevisionOptions(opts);
      } catch { setRevisionOptions([]); }
    })();
  }, [slug]);

  async function createCycle() {
    if (!cycleForm.name.trim() || !cycleForm.revision_id) return;
    setBusy(true); setError(null);
    const opt = revisionOptions.find((o) => String(o.id) === String(cycleForm.revision_id));
    if (!opt) { setError("Select a published revision."); setBusy(false); return; }
    try {
      await qaApi.createCycle(slug, {
        suite_id: opt.suite_id,
        script_revision_id: opt.id,
        name: cycleForm.name,
        environment: cycleForm.environment,
        require_evidence_for_pass: false,
      });
      setCycleForm({ name: "", environment: "UAT", revision_id: "" });
      load();
    } catch (e) { setError(e.message || String(e)); }
    finally { setBusy(false); }
  }

  async function openResults(id) {
    setCycleId(id);
    qaApi.cycleResults(slug, id).then(setResults).catch(() => setResults([]));
  }

  async function setStatus(result, status) {
    try {
      // QA Again's lifecycle rule: FAIL needs an actual result, BLOCKED a
      // blocked_reason, N/A an na_reason. We forward the single "reason"
      // field into whichever slot the target status requires.
      const body = {
        status,
        actual_result_md: result.actual_result_md || "",
        assigned_tester_email: result.assigned_tester_email || "tester",
      };
      if (status === "FAIL") body.actual_result_md = reason;
      if (status === "BLOCKED") body.blocked_reason = reason;
      if (status === "NOT_APPLICABLE") body.na_reason = reason;
      await qaApi.updateResult(slug, cycleId, result.id, body);
      setReason("");
      openResults(cycleId);
    } catch (e) { setError(e.message || String(e)); }
  }

  if (!qaAuthed) return <SignInPrompt service="QA Again" children="Sign in to manage test cycles." />;
  if (!slug) return <Empty title="QA Again is not linked" />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold">Test Cycles</h1>
        <p className="text-sm text-gray-500">Cycles and execution results. Authority: QA Again. OIDA keeps no copy.</p>
      </div>

      {error && <Card className="px-4 py-3 text-sm text-rose-600">{error}</Card>}

      <Card className="px-4 py-3">
        <div className="flex flex-wrap gap-2 text-sm">
          <input className="input flex-1" placeholder="Cycle name *" value={cycleForm.name} onChange={(e) => setCycleForm({ ...cycleForm, name: e.target.value })} />
          <select className="input !w-36" value={cycleForm.environment} onChange={(e) => setCycleForm({ ...cycleForm, environment: e.target.value })}>
            {["DEV", "SIT", "UAT", "PROD"].map((env) => <option key={env}>{env}</option>)}
          </select>
          <select className="input !w-64" value={cycleForm.revision_id} onChange={(e) => setCycleForm({ ...cycleForm, revision_id: e.target.value })}>
            <option value="">Published revision…</option>
            {revisionOptions.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
          </select>
          <button onClick={createCycle} disabled={busy || !cycleForm.name.trim() || !cycleForm.revision_id} className="rounded-lg bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-700 disabled:opacity-50">Create Cycle</button>
        </div>
      </Card>

      <Card>
        <CardHeader title={`Cycles (${cycles?.length ?? "…"})`} />
        {!cycles ? <Loading /> : cycles.length === 0 ? <Empty title="No cycles" /> : (
          <Table head={["Cycle", "Environment", "Status", "Results", ""]}>
            {cycles.map((c) => (
              <Tr key={c.id}>
                <Td className="font-medium text-gray-800">{c.cycle_code ? `${c.cycle_code} — ` : ""}{c.name}</Td>
                <Td className="text-gray-600">{c.environment}</Td>
                <Td><StatusBadge status={c.status} /></Td>
                <Td className="text-gray-600">
                  {c.result_counts ? `P${c.result_counts.PASS} F${c.result_counts.FAIL} B${c.result_counts.BLOCKED} N${c.result_counts.NOT_APPLICABLE}` : "—"}
                </Td>
                <Td className="text-right"><button onClick={() => openResults(c.id)} className="text-xs font-medium text-gray-900 hover:underline">Results</button></Td>
              </Tr>
            ))}
          </Table>
        )}
      </Card>

      {cycleId && (
        <Card>
          <CardHeader title="Cycle results" subtitle="Click a status to record it. FAIL/BLOCKED/N/A need a reason." />
          <div className="flex gap-2 border-b border-gray-100 px-4 py-2 text-sm">
            <input className="input flex-1" placeholder="Actual result / reason (for FAIL, BLOCKED, N/A)" value={reason} onChange={(e) => setReason(e.target.value)} />
          </div>
          {!results ? <Loading /> : results.length === 0 ? <div className="px-4 py-3 text-sm text-gray-400">No results.</div> : (
            <Table head={["Checkpoint", "Status", "Tester", ""]}>
              {results.map((r) => (
                <Tr key={r.id}>
                  <Td className="font-medium text-gray-800">{r.checkpoint_code || r.title || r.id}</Td>
                  <Td><StatusBadge status={r.status} /></Td>
                  <Td className="text-gray-600">{r.assigned_tester_email || "—"}</Td>
                  <Td>
                    <div className="flex flex-wrap gap-1">
                      {RESULT_STATUSES.map((s) => (
                        <button key={s} onClick={() => setStatus(r, s)} className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${r.status === s ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}>{s.replace("_", " ")}</button>
                      ))}
                    </div>
                  </Td>
                </Tr>
              ))}
            </Table>
          )}
        </Card>
      )}
    </div>
  );
}
