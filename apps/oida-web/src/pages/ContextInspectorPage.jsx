import { useEffect, useState } from "react";
import { documentApi, pmApi, qaApi, infraApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, Badge, Loading } from "../components/ui";
import { buildContextEnvelope, detectIntent } from "../lib/contextBuilder";

const EXAMPLES = [
  "Which open requirements currently have no QA coverage?",
  "Which active PM tasks are related to HIGH severity QA defects?",
  "If Direct Connect bandwidth changes to 10 Gbps, which requirements, PM tasks, QA items, and infrastructure components may be affected?",
];

const AUTH_TONE = { DOCUMENT_AGAIN: "blue", PM_AGAIN: "amber", QA_AGAIN: "green", INFRA_AGAIN: "purple" };

export default function ContextInspectorPage() {
  const { project, pm, qa } = useProjectCtx();
  const [question, setQuestion] = useState("");
  const [data, setData] = useState(null);
  const [envelope, setEnvelope] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!project) return;
    const qaSlug = qa?.length ? qa[0].slug : null;
    Promise.all([
      documentApi.listRequirements(project.id).catch(() => []),
      documentApi.projectMemory(project.id).catch(() => null),
      documentApi.traceGraph(project.id).catch(() => ({ edges: [] })),
      pm?.slug ? pmApi.tasks(pm.slug).catch(() => []) : Promise.resolve([]),
      pm?.slug ? pmApi.effortSummary(pm.slug).catch(() => null) : Promise.resolve(null),
      pm?.slug ? pmApi.resources().catch(() => []) : Promise.resolve([]),
      qaSlug ? qaApi.defects(qaSlug).catch(() => []) : Promise.resolve([]),
      qaSlug ? qaApi.suites(qaSlug).catch(() => []) : Promise.resolve([]),
      qaSlug ? qaApi.cycles(qaSlug).catch(() => []) : Promise.resolve([]),
      Promise.resolve([]),
      infraApi.environments().catch(() => []),
      infraApi.designs().catch(() => []),
      infraApi.executionRuns().catch(() => []),
      documentApi.getWorkspaceBindings(project.id).catch(() => null),
    ]).then(([requirements, memory, trace, pmTasks, pmEffort, pmResources, qaDefects, qaSuites, qaCycles, _ignored, infraEnvs, infraDesigns, infraRuns, bindings]) => {
      // Bound Infra design (R14): read flow graph when linked, for component facts.
      const boundPromise = bindings?.infra_design_id
        ? infraApi.getDesign(bindings.infra_design_id).catch(() => null)
        : Promise.resolve(null);
      const firstCycle = qaCycles && qaCycles[0];
      const execPromise = qaSlug && firstCycle
        ? qaApi.cycleResults(qaSlug, firstCycle.id).catch(() => [])
        : Promise.resolve([]);
      // Cases: bounded to the first suite with a PUBLISHED revision.
      const casesPromise = (async () => {
        if (!qaSlug) return [];
        const cases = [];
        for (const s of (qaSuites || []).slice(0, 2)) {
          const revs = await qaApi.revisions(qaSlug, s.id).catch(() => []);
          const pub = (revs || []).find((r) => r.status === "PUBLISHED");
          if (pub) {
            const cs = await qaApi.cases(qaSlug, pub.id).catch(() => []);
            cases.push(...cs);
            break;
          }
        }
        return cases;
      })();
      Promise.all([execPromise, casesPromise, boundPromise]).then(([executions, qaCases, boundDesign]) => {
        const toArr = (v, key) => (Array.isArray(v) ? v : Array.isArray(v && v[key]) ? v[key] : []);
        setData({
          requirements, memory, trace: trace.edges || [], pmTasks, pmEffort, pmResources,
          qaDefects, qaSuites, qaCases, qaCycles, qaExecutions: executions,
          infra: {
            environments: toArr(infraEnvs, "environments"),
            designs: toArr(infraDesigns, "designs"),
            executionRuns: toArr(infraRuns, "executionRuns"),
            boundDesign: boundDesign?.design || boundDesign || null,
          },
        });
      });
    });
  }, [project?.id, pm?.slug, qa?.length]);

  function build() {
    if (!data) return;
    setBusy(true);
    const env = buildContextEnvelope({
      project,
      question,
      requirements: data.requirements,
      clarifications: data.memory?.clarifications || [],
      assumptions: data.memory?.assumptions || [],
      decisions: data.memory?.decisions || [],
      pmTasks: data.pmTasks,
      pmEffort: data.pmEffort,
      pmResources: data.pmResources,
      qaDefects: data.qaDefects,
      qaSuites: data.qaSuites,
      qaCases: data.qaCases,
      qaCycles: data.qaCycles,
      qaExecutions: data.qaExecutions,
      infra: data.infra,
      traceEdges: data.trace,
    });
    setEnvelope(env);
    setBusy(false);
  }

  if (!project) return <Loading />;

  const intent = question ? detectIntent(question) : null;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold">Context Inspector</h1>
        <p className="text-sm text-gray-500">
          Shows what OIDA would give an AI for a question — which records, from which authority, and why. No truth is copied.
        </p>
      </div>

      <Card className="px-4 py-3">
        <div className="flex gap-2">
          <input className="input flex-1" placeholder="Ask a cross-domain question…" value={question} onChange={(e) => setQuestion(e.target.value)} />
          <button onClick={build} disabled={busy || !question.trim()} className="rounded-lg bg-gray-900 px-4 py-1.5 text-xs font-medium text-white hover:bg-gray-700 disabled:opacity-50">
            Build Context
          </button>
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {EXAMPLES.map((e) => (
            <button key={e} onClick={() => setQuestion(e)} className="rounded border border-gray-200 px-2 py-1 text-[11px] text-gray-500 hover:bg-gray-50">{e}</button>
          ))}
        </div>
      </Card>

      {envelope && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Intent" value={envelope.intent} />
            <Stat label="Included records" value={envelope.included_count} />
            <Stat label="Excluded records" value={envelope.excluded.count} />
            <Stat label="Constraint" value="HUMAN-LED" />
          </div>

          <Card>
            <CardHeader title="Included (with authority)" subtitle="Every fact is traceable to its owning service; approval state and fact class are explicit." />
            <ul className="divide-y divide-gray-100">
              {envelope.authority_map.map((f, i) => (
                <li key={i} className="flex flex-wrap items-center gap-2 px-4 py-1.5 text-sm">
                  <Badge tone={AUTH_TONE[f.authority] || "gray"}>{f.authority}</Badge>
                  <span className="font-mono text-xs text-gray-400">{f.fact_type}</span>
                  <span className="font-mono text-[10px] text-gray-400">[{f.fact_class}]</span>
                  <span className="text-gray-800">{f.id}{f.title ? ` — ${f.title}` : ""}{f.content && f.content !== f.id ? ` · ${f.content}` : ""}</span>
                  {f.approval_state && <span className="ml-auto rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500">{f.approval_state}</span>}
                </li>
              ))}
              {envelope.authority_map.length === 0 && <li className="px-4 py-3 text-sm text-gray-400">No records selected for this question.</li>}
            </ul>
          </Card>

          <Card>
            <CardHeader title="Inferred relationships" subtitle="Not authoritative. Labeled proposals that require human review — never traceability truth." />
            {envelope.inferred_relationships.length === 0 ? (
              <div className="px-4 py-3 text-sm text-gray-400">No inferred relationships (evidence-backed links only, or none found).</div>
            ) : (
              <ul className="divide-y divide-gray-100">
                {envelope.inferred_relationships.map((r, i) => (
                  <li key={i} className="px-4 py-2 text-sm">
                    <div className="flex items-center gap-2">
                      <Badge tone="amber">INFERRED</Badge>
                      <span className="text-gray-800">{r.relationship}</span>
                      <span className="ml-auto text-xs text-gray-400">{r.confidence}</span>
                    </div>
                    <div className="mt-1 text-xs text-gray-500">requires_human_review: {String(r.requires_human_review)} · evidence: {JSON.stringify(r.source_evidence)}</div>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card>
            <CardHeader title="Excluded" subtitle="Data minimization — not sent unless needed." />
            <div className="px-4 py-3 text-sm text-gray-600">
              {envelope.excluded.count} records excluded.
              {envelope.excluded.sample.length > 0 && <span className="text-gray-400"> e.g. {envelope.excluded.sample.slice(0, 5).join(", ")}</span>}
            </div>
          </Card>

          <Card>
            <CardHeader title="Authority coverage" />
            <div className="flex flex-wrap gap-2 px-4 py-3">
              {Object.entries(envelope.authority_coverage).map(([k, v]) => (
                <Badge key={k} tone={AUTH_TONE[k] || "gray"}>{k}: {v}</Badge>
              ))}
              {Object.keys(envelope.authority_coverage).length === 0 && <span className="text-sm text-gray-400">None.</span>}
            </div>
          </Card>

          <Card>
            <CardHeader title="Coverage gap" subtitle="Requirements not referenced by any QA case (via case traceability). Derived from QA Again cases — not stored in OIDA." />
            <div className="px-4 py-3 text-sm text-gray-600">
              {!envelope.coverage ? (
                <span className="text-gray-400">No coverage computation available.</span>
              ) : envelope.coverage.uncovered.length === 0 ? (
                <span className="text-emerald-600">All requirements covered.</span>
              ) : (
                <>
                  <span className="font-medium text-gray-800">{envelope.coverage.uncovered.length}</span> of {envelope.coverage.total_requirements} requirements uncovered:
                  <span className="ml-2 font-mono text-xs text-gray-500">{envelope.coverage.uncovered.join(", ")}</span>
                </>
              )}
            </div>
          </Card>

          <details className="rounded-xl border border-gray-200 bg-white">
            <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-gray-700">Context Envelope (JSON)</summary>
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap px-4 py-3 text-xs text-gray-600">{JSON.stringify(envelope, null, 2)}</pre>
          </details>
        </>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white px-4 py-3">
      <div className="text-sm font-semibold text-gray-900">{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  );
}
