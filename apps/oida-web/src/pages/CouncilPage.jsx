import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Users, Play, RotateCcw, CheckCircle2, XCircle, Sparkles, HelpCircle, AlertTriangle, Lightbulb, MessageSquareText } from "lucide-react";
import { documentApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { useProjectContext } from "../hooks/useProjectContext";
import { Card, CardHeader, Badge, Loading, Empty, StatusBadge } from "../components/ui";

const TASK_TYPES = [
  ["GENERAL_REVIEW", "General review"],
  ["CR_RISK_REVIEW", "CR risk review"],
  ["CR_IMPACT_CHALLENGE", "CR impact challenge"],
  ["CR_ASSUMPTION_REVIEW", "CR assumption review"],
  ["CR_QA_REVIEW", "CR QA review"],
  ["CR_INFRA_REVIEW", "CR infra review"],
  ["PM_REVIEW", "PM review"],
  ["QA_REVIEW", "QA review"],
  ["INFRA_REVIEW", "Infra architecture review"],
  ["COMMERCIAL_REVIEW", "Commercial review"],
  ["DEVIL_ADVOCATE", "Devil's advocate"],
];

const RUN_TONE = {
  COMPLETED: "green", FAILED: "red", TIMED_OUT: "red", NOT_CONFIGURED: "gray",
  NOT_AVAILABLE: "gray", DISABLED: "gray", QUEUED: "amber", RUNNING: "blue", CANCELLED: "gray",
};
const SEV_TONE = { HIGH: "red", MEDIUM: "amber", LOW: "gray" };

function FindingCard({ finding, onToSuggestion, converted, onToggleImportant, important }) {
  const providers = finding.providers || [];
  return (
    <li className="rounded-lg border border-gray-100 px-3 py-2 text-sm">
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <div className="font-medium text-gray-800">{finding.title}</div>
          {finding.statement && finding.statement !== finding.title && (
            <div className="mt-0.5 text-xs text-gray-600">{finding.statement}</div>
          )}
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            {finding.finding_type && <Badge tone={finding.finding_type === "RISK" ? "red" : "gray"}>{finding.finding_type}</Badge>}
            {finding.severity && <Badge tone={SEV_TONE[finding.severity] || "gray"}>{finding.severity}</Badge>}
            {providers.length > 0 && <span className="text-[11px] text-gray-400">providers: {providers.join(", ")}</span>}
            {finding.basis && <Badge tone="blue">{finding.basis}</Badge>}
          </div>
          {finding.source_refs?.length > 0 && (
            <div className="mt-1 text-[11px] text-gray-500">
              sources: {finding.source_refs.map((s, i) => (
                <span key={i} className="mr-1.5 font-mono">{s.authority}:{s.source_object_id}</span>
              ))}
            </div>
          )}
        </div>
        <div className="flex shrink-0 flex-col gap-1">
          <button onClick={() => onToggleImportant(finding)} className={`rounded border px-2 py-0.5 text-[11px] ${important ? "border-amber-300 bg-amber-50 text-amber-700" : "border-gray-200 text-gray-500 hover:bg-gray-50"}`}>
            {important ? "★ Important" : "☆ Mark"}
          </button>
          <button onClick={() => onToSuggestion(finding)} disabled={converted} className="rounded border border-gray-200 px-2 py-0.5 text-[11px] text-gray-600 hover:bg-gray-50 disabled:opacity-40">
            → Suggestion
          </button>
        </div>
      </div>
    </li>
  );
}

export default function CouncilPage() {
  const { project, pm, qa } = useProjectCtx();
  const { data, buildEnvelope } = useProjectContext(project, pm, qa);
  const [searchParams] = useSearchParams();

  const [question, setQuestion] = useState(() => searchParams.get("q") || "");
  const [taskType, setTaskType] = useState(() => searchParams.get("task") || "GENERAL_REVIEW");
  const [capabilities, setCapabilities] = useState([]);
  const [result, setResult] = useState(null);       // active consultation
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [important, setImportant] = useState(() => new Set());
  const [converted, setConverted] = useState(() => new Set());
  const [reviewed, setReviewed] = useState(false);

  useEffect(() => {
    if (!project) return;
    documentApi.aiCapabilities().then(setCapabilities).catch(() => setCapabilities([]));
    documentApi.councilConsultations(project.id).then(setHistory).catch(() => setHistory([]));
  }, [project?.id]);

  const mode = useMemo(() => {
    const available = capabilities.filter((p) => ["AVAILABLE", "LOCAL_AVAILABLE"].includes(p.status));
    return {
      available: available.length,
      total: capabilities.length,
      label: available.length >= 2 ? "MULTI-PROVIDER" : available.length === 1 ? "SINGLE_PROVIDER / LOCAL ONLY" : "NONE",
    };
  }, [capabilities]);

  async function consult() {
    if (!project || !question.trim() || !data) return;
    setBusy(true); setError(null); setResult(null); setReviewed(false); setConverted(new Set());
    try {
      const envelope = buildEnvelope(question);
      const res = await documentApi.councilConsult(project.id, {
        task_type: taskType, question: question.trim(), context_envelope: envelope,
      });
      setResult(res);
      documentApi.councilConsultations(project.id).then(setHistory).catch(() => {});
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setBusy(false);
    }
  }

  async function review(decision) {
    if (!result) return;
    try {
      await documentApi.councilReview(result.id, {
        decision, important: [...important], incorrect: [],
      });
      setReviewed(true);
      documentApi.councilConsultations(project.id).then(setHistory).catch(() => {});
    } catch (e) { setError(e.message || String(e)); }
  }

  async function toSuggestion(finding) {
    if (!result) return;
    try {
      await documentApi.councilToSuggestion(result.id, finding);
      setConverted((s) => new Set(s).add(finding.title + (finding.statement || "")));
    } catch (e) { setError(e.message || String(e)); }
  }

  async function checkStale(consultation) {
    if (!data || !consultation?.question) return;
    try {
      const envelope = buildEnvelope(consultation.question);
      if (!envelope) return;
      const stale = await documentApi.councilCheckStale(consultation.id, envelope);
      documentApi.councilConsultations(project.id).then(setHistory).catch(() => {});
      return stale;
    } catch { /* ignore */ }
  }

  async function openHistory(consultation) {
    setResult(consultation);
    setReviewed(Boolean(consultation.human_review));
    setQuestion(consultation.question);
    setTaskType(consultation.task_type);
    if (!consultation.stale) await checkStale(consultation);
  }

  if (!project) return <Loading />;

  const agg = result?.aggregation;
  const authorityCoverage = result?.context_snapshot?.authority_coverage || {};
  const coverageKeys = Object.keys(authorityCoverage);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold">Council</h1>
        <p className="text-sm text-gray-500">
          Independent AI consultants review the same question with the same context — no peer answers. Their perspectives are organized, never turned into project truth. The human decides.
        </p>
      </div>

      <Card className="px-4 py-3">
        <div className="flex items-center gap-2">
          <Badge tone={mode.available >= 2 ? "green" : "amber"}>Council Mode: {mode.label}</Badge>
          <span className="text-xs text-gray-500">{mode.available} of {mode.total} providers available</span>
        </div>
        <div className="mt-3 grid gap-2">
          <textarea className="input min-h-20 w-full" placeholder="Question / task for the Council…" value={question} onChange={(e) => setQuestion(e.target.value)} />
          <div className="flex flex-wrap items-center gap-2">
            <select className="input w-fit" value={taskType} onChange={(e) => setTaskType(e.target.value)}>
              {TASK_TYPES.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
            </select>
            <button onClick={consult} disabled={busy || !question.trim() || !data} className="flex items-center gap-1.5 rounded-lg bg-gray-900 px-4 py-1.5 text-xs font-medium text-white hover:bg-gray-700 disabled:opacity-50">
              <Play size={14} /> Consult Council
            </button>
            {busy && <span className="text-xs text-gray-500">Running independent providers in parallel…</span>}
          </div>
        </div>
        {error && <div className="mt-2 text-xs text-rose-600">{error}</div>}
      </Card>

      {/* Provider run cards */}
      <Card>
        <CardHeader title="Provider runs" subtitle="Every provider is shown — unavailable is never hidden." />
        <div className="grid gap-2 px-4 py-3 md:grid-cols-2 lg:grid-cols-5">
          {(result ? result.runs : capabilities).map((p) => {
            const run = result?.runs?.find((r) => r.provider_id === p.provider_id);
            const cap = capabilities.find((c) => c.provider_id === (p.provider_id || p.id));
            const status = run?.status || p.status || cap?.status || "NOT_CONFIGURED";
            const model = run?.model || p.model || cap?.model;
            return (
              <div key={p.provider_id || p.id} className="rounded-lg border border-gray-100 px-3 py-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-gray-800">{p.display_name || cap?.display_name || p.provider_id}</span>
                  <Badge tone={RUN_TONE[status] || "gray"}>{status}</Badge>
                </div>
                {model && <div className="mt-0.5 text-[11px] text-gray-500">model: {model}</div>}
                {run?.latency_ms ? <div className="text-[11px] text-gray-400">latency: {(run.latency_ms / 1000).toFixed(1)}s</div> : null}
                {run?.findings ? <div className="text-[11px] text-gray-500">findings: {run.findings.length}</div> : null}
                {(status === "NOT_AVAILABLE" && p.reason) ? <div className="mt-0.5 text-[11px] text-gray-400">{p.reason}</div> : null}
                {(status === "NOT_CONFIGURED") && <div className="mt-0.5 text-[11px] text-gray-400">No API key configured</div>}
                {run?.error && <div className="mt-0.5 truncate text-[11px] text-rose-500" title={run.error}>{run.error}</div>}
              </div>
            );
          })}
        </div>
      </Card>

      {/* Context data-minimization evidence */}
      {result && (
        <Card className="px-4 py-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-gray-400">Context sent (data minimization)</div>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {coverageKeys.map((k) => (
              <Badge key={k} tone="gray">{k}: {authorityCoverage[k]}</Badge>
            ))}
            <span className="text-[11px] text-gray-400">snapshot {result.context_snapshot?.context_hash}</span>
          </div>
        </Card>
      )}

      {/* Council result */}
      {agg && (
        <div className="space-y-4">
          <Card>
            <CardHeader
              title="Council result"
              subtitle={agg.note}
              right={<Badge tone={agg.aggregation_mode === "MULTI_PROVIDER" ? "green" : "amber"}>{agg.aggregation_mode}</Badge>}
            />
            <div className="px-4 py-3 text-xs text-gray-500">
              Completed providers: {agg.completed_providers?.join(", ") || "none"} · Consensus {agg.consensus?.length || 0} · Disagreements {agg.disagreements?.length || 0} · Unique {agg.unique_insights?.length || 0}
            </div>
          </Card>

          {agg.consensus?.length > 0 && (
            <Card>
              <CardHeader title="Consensus" subtitle="Advisory only — AI agreement is NOT project truth. Authority records win." />
              <ul className="space-y-1.5 px-4 py-3">
                {agg.consensus.map((f, i) => (
                  <FindingCard key={"c" + i} finding={f} onToSuggestion={toSuggestion} onToggleImportant={(x) => setImportant((s) => { const n = new Set(s); n.has(x.title) ? n.delete(x.title) : n.add(x.title); return n; })} important={important.has(f.title)} converted={converted.has(f.title + (f.statement || ""))} />
                ))}
              </ul>
            </Card>
          )}

          {agg.disagreements?.length > 0 && (
            <Card>
              <CardHeader title="Disagreements" subtitle="A feature, not a defect — where models differ." />
              <ul className="space-y-1.5 px-4 py-3">
                {agg.disagreements.map((f, i) => (
                  <li key={"d" + i} className="rounded-lg border border-violet-100 bg-violet-50/50 px-3 py-2 text-sm">
                    <div className="font-medium text-gray-800">{f.title}</div>
                    <div className="mt-1 flex flex-wrap gap-1.5">
                      {Object.entries(f.severities || {}).map(([prov, sev]) => (
                        <Badge key={prov} tone={SEV_TONE[sev] || "gray"}>{prov}: {sev}</Badge>
                      ))}
                    </div>
                    {f.source_refs?.length > 0 && <div className="mt-1 text-[11px] text-gray-500">sources: {f.source_refs.map((s, i) => <span key={i} className="mr-1 font-mono">{s.authority}:{s.source_object_id}</span>)}</div>}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {agg.unique_insights?.length > 0 && (
            <Card>
              <CardHeader title="Unique insights" subtitle="A single model raised these." />
              <ul className="space-y-1.5 px-4 py-3">
                {agg.unique_insights.map((f, i) => (
                  <FindingCard key={"u" + i} finding={f} onToSuggestion={toSuggestion} onToggleImportant={(x) => setImportant((s) => { const n = new Set(s); n.has(x.title) ? n.delete(x.title) : n.add(x.title); return n; })} important={important.has(f.title)} converted={converted.has(f.title + (f.statement || ""))} />
                ))}
              </ul>
            </Card>
          )}

          {(agg.unknown_areas?.length > 0 || agg.questions?.length > 0 || agg.recommendations?.length > 0) && (
            <Card>
              <CardHeader title="Unknowns · Questions · Recommendations" />
              <div className="grid gap-3 px-4 py-3 md:grid-cols-3">
                <div>
                  <div className="mb-1 flex items-center gap-1 text-xs font-semibold text-gray-500"><HelpCircle size={12} /> Unknowns</div>
                  <ul className="space-y-1 text-xs text-gray-600">
                    {agg.unknown_areas?.map((u, i) => <li key={i}>• {u.statement}</li>)}
                    {(!agg.unknown_areas || agg.unknown_areas.length === 0) && <li className="text-gray-400">none</li>}
                  </ul>
                </div>
                <div>
                  <div className="mb-1 flex items-center gap-1 text-xs font-semibold text-gray-500"><MessageSquareText size={12} /> Questions</div>
                  <ul className="space-y-1 text-xs text-gray-600">
                    {agg.questions?.map((q, i) => <li key={i}>• {q.question}</li>)}
                    {(!agg.questions || agg.questions.length === 0) && <li className="text-gray-400">none</li>}
                  </ul>
                </div>
                <div>
                  <div className="mb-1 flex items-center gap-1 text-xs font-semibold text-gray-500"><Lightbulb size={12} /> Recommendations</div>
                  <ul className="space-y-1 text-xs text-gray-600">
                    {agg.recommendations?.map((r, i) => <li key={i}>• {r.recommendation}</li>)}
                    {(!agg.recommendations || agg.recommendations.length === 0) && <li className="text-gray-400">none</li>}
                  </ul>
                </div>
              </div>
            </Card>
          )}

          {/* Human review */}
          <Card className="px-4 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">Human review</span>
              {reviewed ? (
                <Badge tone="green">Reviewed — {result.human_review?.decision}</Badge>
              ) : (
                <>
                  <button onClick={() => review("USEFUL")} className="flex items-center gap-1 rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-100"><CheckCircle2 size={14} /> Accept as useful</button>
                  <button onClick={() => review("REJECTED")} className="flex items-center gap-1 rounded-lg border border-rose-300 bg-rose-50 px-3 py-1 text-xs font-medium text-rose-700 hover:bg-rose-100"><XCircle size={14} /> Reject</button>
                </>
              )}
              <button onClick={consult} disabled={busy || !data} className="flex items-center gap-1 rounded-lg border border-gray-200 px-3 py-1 text-xs text-gray-600 hover:bg-gray-50"><RotateCcw size={14} /> Re-run Council</button>
              <span className="text-[11px] text-gray-400">Findings are advisory — convert to a Suggestion to enter the human-led workflow.</span>
            </div>
          </Card>
        </div>
      )}

      {/* History */}
      <Card>
        <CardHeader title="Consultation history" subtitle="Old consultations are never overwritten." />
        {history.length === 0 ? (
          <div className="px-4 py-3"><Empty title="No consultations yet" /></div>
        ) : (
          <ul className="divide-y divide-gray-100">
            {history.map((c) => (
              <li key={c.id} className="flex items-center gap-2 px-4 py-2 text-sm">
                <button onClick={() => openHistory(c)} className="min-w-0 flex-1 text-left">
                  <div className="truncate font-medium text-gray-800 hover:underline">{c.question}</div>
                  <div className="text-[11px] text-gray-400">{c.task_type} · {new Date(c.created_at).toLocaleString()} · {c.aggregation?.aggregation_mode}</div>
                </button>
                {c.stale && <Badge tone="amber">stale</Badge>}
                {c.human_review && <Badge tone="green">{c.human_review.decision}</Badge>}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
