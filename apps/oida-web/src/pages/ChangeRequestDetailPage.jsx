import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { documentApi, pmApi, qaApi, infraApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { buildCrImpact } from "../lib/crImpact";
import { Card, CardHeader, StatusBadge, Badge, Loading, formatDateTime } from "../components/ui";

const LEVEL_TONE = { DIRECT: "red", INDIRECT: "amber", POTENTIAL: "violet" };
const CONF_TONE = { HIGH: "green", MEDIUM: "blue", LOW: "amber", UNKNOWN: "gray" };
const BASIS_TONE = { PM_RECORDED: "green", DOCUMENT_RECORDED: "blue", QA_RECORDED: "green", INFRA_RECORDED: "purple", CALCULATED: "blue", AI_ESTIMATE: "amber", MANUAL_INPUT: "gray", HUMAN_OVERRIDE: "violet", UNKNOWN: "gray" };

function SourceLabel({ source }) {
  const tone = source === "SYSTEM-DERIVED" ? "green" : source === "HUMAN-ADDED" ? "blue" : "amber";
  return <Badge tone={tone}>{source || "—"}</Badge>;
}

function ImpactItem({ item, decision, onDecide }) {
  return (
    <li className="rounded-lg border border-gray-100 px-3 py-2 text-sm">
      <div className="flex items-center gap-2">
        <Badge tone={LEVEL_TONE[item.level] || "gray"}>{item.level}</Badge>
        <span className="font-medium text-gray-800">{item.display_name || item.id}</span>
        <span className="text-xs text-gray-400">{item.object_type}</span>
        <span className="ml-auto"><SourceLabel source={item.source} /></span>
      </div>
      <div className="mt-1 text-xs text-gray-600">
        <span className="font-medium">Reason:</span> {item.reason}
      </div>
      {item.path && item.path.length > 0 && (
        <div className="mt-1 text-xs text-gray-500">
          <span className="font-medium">Path:</span>{" "}
          {item.path.map((p, i) => (
            <span key={i}>{i > 0 && <span className="mx-1 text-gray-400">↓</span>}<span className="font-mono">{p}</span></span>
          ))}
        </div>
      )}
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <DecisionButton active={decision === "CONFIRMED"} onClick={() => onDecide(item.id, "CONFIRMED")} tone="green">✓ Confirm</DecisionButton>
        <DecisionButton active={decision === "NOT_IMPACTED"} onClick={() => onDecide(item.id, "NOT_IMPACTED")} tone="red">× Not impacted</DecisionButton>
        {decision && <span className="text-xs text-gray-500">· {decision.replaceAll("_", " ")}</span>}
      </div>
    </li>
  );
}

function DecisionButton({ active, onClick, tone, children }) {
  const activeCls = { green: "bg-emerald-600 text-white border-emerald-600", red: "bg-rose-600 text-white border-rose-600" };
  const idleCls = "border-gray-300 bg-white text-gray-700 hover:bg-gray-50";
  return (
    <button onClick={onClick} className={`rounded-lg border px-2 py-1 text-xs font-medium ${active ? activeCls[tone] : idleCls}`}>
      {children}
    </button>
  );
}

export default function ChangeRequestDetailPage() {
  const { projectId, crId } = useParams();
  const { project, pm, qa } = useProjectCtx();
  const [cr, setCr] = useState(null);
  const [impact, setImpact] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [decisions, setDecisions] = useState({});
  const [humanAdded, setHumanAdded] = useState([]);
  const [newImpact, setNewImpact] = useState({ display_name: "", object_type: "", reason: "" });
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [xsImpact, setXsImpact] = useState(null);
  const [xsBusy, setXsBusy] = useState(false);

  function loadCr() {
    documentApi.getChangeRequest(crId).then(setCr).catch((e) => setError(e.message));
    documentApi.crImpact(crId).then(setImpact).catch(() => setImpact(null));
  }
  function loadAnalysis() {
    documentApi.getCrImpactAnalysis(crId).then((a) => { setAnalysis(a); seedDecisions(a); }).catch(() => setAnalysis(null));
  }

  function seedDecisions(a) {
    const d = {};
    const review = a?.result?.review || {};
    Object.entries(review.decisions || {}).forEach(([id, v]) => { d[id] = v.decision; });
    setDecisions(d);
  }

  useEffect(() => { loadCr(); loadAnalysis(); }, [crId]);

  // Cross-service impact intelligence (deterministic, live, no-key safe).
  useEffect(() => {
    if (!project?.id) return;
    const pmSlug = pm?.slug;
    const qaSlug = qa?.length ? qa[0].slug : null;
    (async () => {
      setXsBusy(true);
      try {
        const [requirements, memory, pmFunctions, pmTasks, pmEffort, pmResources, pmStatus,
               qaSuites, qaCycles, qaDefects, infraEnvs, infraDesigns, bindings] = await Promise.all([
          documentApi.listRequirements(project.id).catch(() => []),
          documentApi.projectMemory(project.id).catch(() => null),
          pmSlug ? pmApi.functions(pmSlug).catch(() => []) : Promise.resolve([]),
          pmSlug ? pmApi.tasks(pmSlug).catch(() => []) : Promise.resolve([]),
          pmSlug ? pmApi.effortSummary(pmSlug).catch(() => null) : Promise.resolve(null),
          pmSlug ? pmApi.resources().catch(() => []) : Promise.resolve([]),
          pmSlug ? pmApi.pmStatus(pmSlug).catch(() => ({})) : Promise.resolve({}),
          qaSlug ? qaApi.suites(qaSlug).catch(() => []) : Promise.resolve([]),
          qaSlug ? qaApi.cycles(qaSlug).catch(() => []) : Promise.resolve([]),
          qaSlug ? qaApi.defects(qaSlug).catch(() => []) : Promise.resolve([]),
          infraApi.environments().catch(() => []),
          infraApi.designs().catch(() => []),
          documentApi.getWorkspaceBindings(project.id).catch(() => null),
        ]);
        // Bound Infra design (R14): read its flow graph when linked.
        let boundDesign = null;
        const boundId = bindings?.infra_design_id;
        if (boundId) {
          const d = await infraApi.getDesign(boundId).catch(() => null);
          boundDesign = d?.design || d || null;
        }
        // QA cases: first published revision of the current scope (bounded).
        let qaCases = [];
        if (qaSlug) {
          for (const s of (qaSuites || []).slice(0, 2)) {
            const revs = await qaApi.revisions(qaSlug, s.id).catch(() => []);
            const pub = (revs || []).find((r) => r.status === "PUBLISHED");
            if (pub) { qaCases = await qaApi.cases(qaSlug, pub.id).catch(() => []); break; }
          }
        }
        const toArr = (v, key) => (Array.isArray(v) ? v : Array.isArray(v && v[key]) ? v[key] : []);
        const result = buildCrImpact({
          cr,
          document: {
            requirements,
            clarifications: memory?.clarifications || [],
            assumptions: memory?.assumptions || [],
          },
          pm: { functions: pmFunctions, tasks: pmTasks, effortSummary: pmEffort, resources: pmResources, pmStatus },
          qa: { suites: qaSuites, cases: qaCases, cycles: qaCycles, defects: qaDefects },
          infra: { environments: toArr(infraEnvs, "environments"), designs: toArr(infraDesigns, "designs"), boundDesign },
        });
        setXsImpact(result);
      } catch (e) {
        setError(e.message || String(e));
      } finally {
        setXsBusy(false);
      }
    })();
  }, [project?.id, pm?.slug, qa?.length, cr?.requested_change]);

  async function analyze() {
    setBusy(true); setError(null);
    try { const a = await documentApi.analyzeCrImpact(crId); setAnalysis(a); seedDecisions(a); loadCr(); }
    catch (e) { setError(e.message || String(e)); }
    finally { setBusy(false); }
  }

  async function submitReview(finalize) {
    setBusy(true); setError(null);
    try {
      const decisionObjs = Object.fromEntries(
        Object.entries(decisions).map(([id, d]) => [id, { decision: d }])
      );
      const a = await documentApi.reviewCrImpactAnalysis(crId, analysis.id, {
        decisions: decisionObjs,
        human_added: humanAdded,
        comments: comment ? [comment] : [],
        finalize,
      });
      setAnalysis(a); setComment(""); setHumanAdded([]); loadCr();
    } catch (e) { setError(e.message || String(e)); }
    finally { setBusy(false); }
  }

  async function approve(decision) {
    try { setImpact(await documentApi.crCustomerApproval(crId, { decision, approved_by: "Owner", note: "Customer decision recorded" })); loadCr(); }
    catch (e) { setError(e.message); }
  }

  async function transition(toStatus, note) {
    setBusy(true); setError(null);
    try {
      await documentApi.transitionCr(crId, toStatus, note);
      loadCr();
    } catch (e) { setError(e.message || String(e)); }
    finally { setBusy(false); }
  }

  function decide(id, d) {
    setDecisions((prev) => ({ ...prev, [id]: d }));
  }

  function addHumanImpact() {
    if (!newImpact.display_name.trim()) return;
    setHumanAdded((h) => [...h, { display_name: newImpact.display_name, object_type: newImpact.object_type, reason: newImpact.reason, level: "DIRECT" }]);
    setNewImpact({ display_name: "", object_type: "", reason: "" });
  }

  if (error && !cr) return <Card className="px-6 py-10 text-center text-sm text-rose-600">{error}</Card>;
  if (!cr) return <Loading />;

  const r = analysis?.result || {};
  const known = r.known_impact || [];
  const potential = r.potential_impact || [];
  const unknown = r.unknown_areas || [];
  const review = r.review || {};
  const fi = impact?.function_impact;
  const ei = impact?.effort_impact;
  const ti = impact?.timeline_impact;
  const qi = impact?.qa_impact;
  const ii = impact?.infra_impact;

  return (
    <div className="space-y-5">
      <div>
        <Link to={`/projects/${projectId}/changes`} className="text-sm text-gray-500 hover:text-gray-800">← Changes</Link>
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <h1 className="text-lg font-bold">{cr.code}</h1>
          <StatusBadge status={cr.status} />
          {impact?.classification && <Badge tone="violet">{impact.classification}</Badge>}
          {analysis?.stale && <Badge tone="amber">STALE — re-analysis required</Badge>}
        </div>
        <p className="mt-1 text-sm text-gray-600">{cr.title && <span className="font-medium text-gray-800">{cr.title}: </span>}{cr.requested_change}</p>
        <div className="mt-1 text-xs text-gray-400">
          Requested by {cr.requested_by || "—"} · {cr.requested_date || "—"} · {cr.reason && <span>“{cr.reason}”</span>}
        </div>
      </div>

      {error && <Card className="px-4 py-3 text-sm text-rose-600">{error}</Card>}

      {/* R13 — lifecycle transitions (human-driven, guarded by Document Again) */}
      <Card className="px-4 py-3">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="font-semibold uppercase tracking-wide text-gray-500">Lifecycle</span>
          <span className="font-mono text-gray-400">DRAFT → OPEN → NEEDS_CLARIFICATION → IMPACT_ANALYZED → UNDER_HUMAN_REVIEW → INTERNAL_REVIEW_COMPLETE → ACCEPTED → IMPLEMENTATION_PLANNED → IMPLEMENTED → CLOSED</span>
          <span className="ml-auto flex flex-wrap gap-1.5">
            {[
              ["OPEN", "Open"],
              ["NEEDS_CLARIFICATION", "Needs clarification"],
              ["UNDER_HUMAN_REVIEW", "Under review"],
              ["IMPLEMENTATION_PLANNED", "Plan implementation"],
              ["CLOSED", "Close"],
            ].map(([s, label]) => (
              <button key={s} onClick={() => transition(s, null)} disabled={busy || cr.status === s}
                className={`rounded border px-2 py-1 text-[11px] font-medium ${cr.status === s ? "border-gray-900 bg-gray-900 text-white" : "border-gray-300 text-gray-600 hover:bg-gray-50"} disabled:opacity-40`}>
                {label}
              </button>
            ))}
          </span>
        </div>
        <div className="mt-1 text-[11px] text-gray-400">Every transition is a human action against Document Again; the state machine rejects illegal jumps (e.g. no DRAFT → APPROVED).</div>
      </Card>

      {/* R13 — cross-service impact intelligence */}
      <Card>
        <CardHeader
          title="Impact Intelligence (cross-service)"
          subtitle="Deterministic projection of live PM / QA / Infra / Document truth. Every line carries a basis; nothing is persisted in OIDA."
          right={<div className="flex items-center gap-2">
            {cr?.code && (
              <Link to={`/projects/${project.id}/council?task=CR_RISK_REVIEW&q=${encodeURIComponent(`Review ${cr.code}: ${cr.requested_change || cr.title || ""}. Identify risks, assumptions, missing evidence, and areas where the impact estimate may be optimistic.`)}`}
                className="rounded border border-gray-300 px-2 py-1 text-[11px] font-medium text-gray-700 hover:bg-gray-50">
                Ask Council to Review Impact
              </Link>
            )}
            {xsBusy ? <span className="text-xs text-gray-400">Analyzing…</span> : xsImpact && <Badge tone="gray">live · {xsImpact.generated_at?.slice(11, 19)}</Badge>}
          </div>}
        />
        {!xsImpact ? (
          <div className="px-4 py-3 text-sm text-gray-500">Loading live project truth from bounded authorities…</div>
        ) : (
          <div className="space-y-4 px-4 py-3">
            {/* Executive summary */}
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              <Sum label="Functions" value={`${xsImpact.summary.function.affected} affected · ${xsImpact.summary.function.new_candidates} new candidates`} />
              <Sum label="Requirements" value={`${xsImpact.summary.requirements.revised_proposed} revisions proposed`} />
              <Sum label="PM / Effort" value={`${xsImpact.summary.pm.tasks_affected} tasks · ${xsImpact.summary.pm.effort ?? "—"} pd`} />
              <Sum label="Timeline" value={xsImpact.summary.timeline} />
              <Sum label="QA" value={`${xsImpact.summary.qa.cases_revise} cases · ${xsImpact.summary.qa.regression_cycles} cycles`} />
              <Sum label="Infra" value={xsImpact.summary.infra.bound_design ? `Bound ${xsImpact.summary.infra.bound_design} · ${xsImpact.summary.infra.components_total} comp · ${xsImpact.summary.infra.connections_total} conn` : `${xsImpact.summary.infra.designs_affected} designs · ${xsImpact.summary.infra.environments_affected} envs`} />
              <Sum label="Commercial" value={xsImpact.summary.commercial} />
              <Sum label="Open questions" value={xsImpact.summary.open_questions} />
            </div>

            <details open className="rounded-lg border border-gray-200">
              <summary className="cursor-pointer px-3 py-2 text-sm font-semibold text-gray-700">Functions</summary>
              <div className="px-3 pb-3 text-sm">
                {xsImpact.function_impact.modified.length === 0 ? <Muted text="No PM function matched the CR text — scope UNKNOWN until a human maps it." /> : (
                  <ul className="space-y-1">
                    {xsImpact.function_impact.modified.map((m, i) => (
                      <li key={i} className="flex items-center gap-2 text-xs">
                        <Badge tone="amber">MODIFIED</Badge><span className="font-medium text-gray-800">{m.function}</span>
                        <Badge tone={BASIS_TONE[m.basis] || "gray"}>{m.basis}</Badge>
                        <span className="text-gray-400">terms: {m.matched_terms.join(", ")} · INFERRED</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </details>

            <details open className="rounded-lg border border-gray-200">
              <summary className="cursor-pointer px-3 py-2 text-sm font-semibold text-gray-700">Requirements</summary>
              <div className="px-3 pb-3 text-sm">
                {xsImpact.requirement_impact.revised.length === 0 ? <Muted text="No approved requirement matched the CR text." /> : (
                  <ul className="space-y-1.5">
                    {xsImpact.requirement_impact.revised.map((r, i) => (
                      <li key={i} className="rounded border border-gray-100 px-2 py-1.5 text-xs">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-medium text-gray-800">{r.code}</span>
                          <Badge tone="amber">{r.state}</Badge>
                          <Badge tone={BASIS_TONE[r.basis] || "gray"}>{r.basis}</Badge>
                        </div>
                        <div className="mt-1 text-gray-600">{r.proposed}</div>
                      </li>
                    ))}
                  </ul>
                )}
                {xsImpact.requirement_impact.invalid_assumptions.length > 0 && (
                  <div className="mt-2 text-xs text-gray-500">Assumptions possibly invalidated: {xsImpact.requirement_impact.invalid_assumptions.map((a) => a.content).join("; ")}</div>
                )}
              </div>
            </details>

            <details open className="rounded-lg border border-gray-200">
              <summary className="cursor-pointer px-3 py-2 text-sm font-semibold text-gray-700">PM tasks & effort</summary>
              <div className="px-3 pb-3 text-sm">
                {xsImpact.pm_impact.affected_tasks.length === 0 ? <Muted text="No PM task matched the CR text." /> : (
                  <ul className="space-y-1">
                    {xsImpact.pm_impact.affected_tasks.map((t, i) => (
                      <li key={i} className="flex items-center gap-2 text-xs">
                        <Badge tone="amber">MODIFIED</Badge><span className="font-medium text-gray-800">{t.title}</span>
                        <Badge tone={BASIS_TONE[t.basis] || "gray"}>{t.basis}</Badge>
                        <span className="text-gray-400">INFERRED</span>
                      </li>
                    ))}
                  </ul>
                )}
                <div className="mt-2 flex items-center gap-2 text-xs">
                  <span className="font-semibold text-gray-600">Effort:</span>
                  {xsImpact.effort_impact.total_person_days != null
                    ? <><span className="font-medium text-gray-800">{xsImpact.effort_impact.total_person_days} person-days</span>
                        <Badge tone={BASIS_TONE[xsImpact.effort_impact.basis] || "gray"}>{xsImpact.effort_impact.basis}</Badge>
                        {xsImpact.effort_impact.formula && <span className="font-mono text-gray-400">{xsImpact.effort_impact.formula}</span>}</>
                    : <span className="text-gray-600">PM-recorded effort summary (see below).</span>}
                </div>
                {xsImpact.effort_impact.note && <div className="mt-1 text-[11px] text-gray-400">{xsImpact.effort_impact.note}</div>}
              </div>
            </details>

            <details className="rounded-lg border border-gray-200">
              <summary className="cursor-pointer px-3 py-2 text-sm font-semibold text-gray-700">Timeline · QA · Infra · Commercial</summary>
              <div className="grid gap-3 px-3 pb-3 text-xs md:grid-cols-2">
                <div>
                  <div className="font-semibold text-gray-500">Timeline</div>
                  <div className="mt-1 font-medium text-gray-800">{xsImpact.timeline_impact.status}</div>
                  <div className="text-gray-500">{xsImpact.timeline_impact.reason}</div>
                  <Badge tone={BASIS_TONE[xsImpact.timeline_impact.basis] || "gray"}>{xsImpact.timeline_impact.basis}</Badge>
                </div>
                <div>
                  <div className="font-semibold text-gray-500">QA</div>
                  <div className="mt-1 text-gray-700">Revise {xsImpact.qa_impact.revise.length} · Regression {xsImpact.qa_impact.regression.length} · Relevant defects {xsImpact.qa_impact.relevant_defects.length}</div>
                  <div className="text-gray-500">{xsImpact.qa_impact.signoff.note}</div>
                </div>
                <div>
                  <div className="font-semibold text-gray-500">Infra</div>
                  <div className="mt-1 text-gray-700">
                    {xsImpact.infra_impact.bound_design ? (
                      <>Bound {xsImpact.infra_impact.bound_design.design_id} · {xsImpact.infra_impact.components.length} components · {xsImpact.infra_impact.connections.recorded} connections</>
                    ) : (
                      <>Designs affected {xsImpact.infra_impact.affected_designs.length} · Environments {xsImpact.infra_impact.affected_environments.length}</>
                    )}
                  </div>
                  <div className="text-gray-500">{xsImpact.infra_impact.note}</div>
                  {xsImpact.infra_impact.components.length > 0 && (
                    <ul className="mt-1 space-y-0.5">
                      {xsImpact.infra_impact.components.map((c) => (
                        <li key={c.node_id} className="flex items-center gap-1.5">
                          <Badge tone={c.change_type === "MODIFIED" ? "amber" : "gray"}>{c.change_type}</Badge>
                          <span className="font-mono">{c.service || c.node_id}</span>
                          <span className="text-gray-400">{c.category} · {c.provider}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div>
                  <div className="font-semibold text-gray-500">Commercial</div>
                  <div className="mt-1 font-medium text-gray-800">{xsImpact.commercial_impact.value_status}</div>
                  <div className="text-gray-500">{xsImpact.commercial_impact.note}</div>
                </div>
              </div>
            </details>

            <section>
              <SectionHead tone="amber" label={`OPEN QUESTIONS (${xsImpact.open_questions.length})`} note="must be answered before approval" />
              <ul className="space-y-1">
                {xsImpact.open_questions.map((q, i) => (
                  <li key={i} className="rounded border border-amber-100 bg-amber-50 px-3 py-1.5 text-xs text-gray-700">• {q}</li>
                ))}
              </ul>
            </section>

            {/* Traceability chain */}
            <section>
              <SectionHead tone="blue" label="TRACEABILITY CHAIN" note="every hop is evidenced; inference never becomes explicit truth" />
              <div className="font-mono text-[11px] leading-5 text-gray-600">
                Customer Request → {cr.code} ({cr.status}) → Concern/Question → Customer Answer → AI Interpretation → Impact Analysis → Human Review → Approved Change → Requirement Revision → PM Tasks/Effort → QA Revision/Regression → Infra Change → Implementation → Validation → Sign-off
              </div>
            </section>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader
          title="Impact Analysis"
          subtitle={analysis ? `Analyzed against ${analysis.baseline_name || "current baseline"}` : "Run analysis to see known, potential and unknown impact."}
          right={
            <button onClick={analyze} disabled={busy} className="rounded-lg border border-gray-300 bg-gray-100 px-3 py-1.5 text-xs font-medium text-gray-900 hover:bg-gray-200 disabled:opacity-50">
              {analysis ? "Re-run Analysis" : "Analyze Impact"}
            </button>
          }
        />
        <div className="space-y-4 px-4 py-3">
          {!analysis ? (
            <p className="text-sm text-gray-500">No impact analysis yet. The system never claims impact from memory.</p>
          ) : (
            <>
              <div className="grid grid-cols-3 gap-3 text-sm">
                <div className="rounded-lg border border-gray-100 p-2">
                  <div className="text-xs text-gray-400">Impact confidence</div>
                  <Badge tone={CONF_TONE[analysis.confidence] || "gray"}>{analysis.confidence}</Badge>
                </div>
                <div className="rounded-lg border border-gray-100 p-2">
                  <div className="text-xs text-gray-400">Trace coverage</div>
                  <div className="font-medium text-gray-800">{analysis.coverage_status}</div>
                  <div className="text-xs text-gray-500">{r.trace_coverage?.confirmed_relationships || 0} confirmed · {r.trace_coverage?.inferred_or_unresolved || 0} inferred/unresolved</div>
                </div>
                <div className="rounded-lg border border-gray-100 p-2">
                  <div className="text-xs text-gray-400">Human review</div>
                  <div className="font-medium text-gray-800">{String(analysis.review_state).replaceAll("_", " ")}</div>
                  {analysis.reviewed_by && <div className="text-xs text-gray-500">by {analysis.reviewed_by}</div>}
                </div>
              </div>

              <section>
                <SectionHead tone="green" label={`KNOWN IMPACT (${known.length})`} note="explicit trace-derived" />
                {known.length === 0 ? <Empty2 text="No known impact." /> : (
                  <ul className="space-y-2">{known.map((it) => <ImpactItem key={it.id} item={it} decision={decisions[it.id]} onDecide={decide} />)}</ul>
                )}
              </section>

              <section>
                <SectionHead tone="amber" label={`POTENTIAL IMPACT (${potential.length})`} note="inferred / indirect — needs decision" />
                {potential.length === 0 ? <Empty2 text="No potential impact." /> : (
                  <ul className="space-y-2">{potential.map((it) => <ImpactItem key={it.id} item={it} decision={decisions[it.id]} onDecide={decide} />)}</ul>
                )}
              </section>

              <section>
                <SectionHead tone="gray" label={`UNKNOWN AREAS (${unknown.length})`} note="no reliable relationship exists" />
                {unknown.length === 0 ? <Empty2 text="No unknown areas." /> : (
                  <ul className="space-y-1.5">
                    {unknown.map((u, i) => (
                      <li key={i} className="rounded-lg border border-gray-100 px-3 py-2 text-sm">
                        <div className="font-medium text-gray-800">{u.label}</div>
                        <div className="text-xs text-gray-500">{u.reason}</div>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {review.human_added?.length > 0 && (
                <section>
                  <SectionHead tone="blue" label={`HUMAN-ADDED (${review.human_added.length})`} note="manual review additions — audited, not system-derived" />
                  <ul className="space-y-1.5">
                    {review.human_added.map((h, i) => (
                      <li key={i} className="rounded-lg border border-sky-100 bg-sky-50 px-3 py-2 text-sm">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-gray-800">{h.display_name}</span>
                          <span className="text-xs text-gray-400">{h.object_type}</span>
                          <span className="ml-auto"><SourceLabel source="HUMAN-ADDED" /></span>
                        </div>
                        <div className="mt-0.5 text-xs text-gray-600">{h.reason} · by {h.added_by}</div>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              <section className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Human review</div>
                <div className="mt-2 grid gap-2 text-sm">
                  <input className="input" placeholder="Add missing impact — object name" value={newImpact.display_name} onChange={(e) => setNewImpact({ ...newImpact, display_name: e.target.value })} />
                  <div className="grid grid-cols-2 gap-2">
                    <input className="input" placeholder="Object type (e.g. Architecture)" value={newImpact.object_type} onChange={(e) => setNewImpact({ ...newImpact, object_type: e.target.value })} />
                    <input className="input" placeholder="Reason" value={newImpact.reason} onChange={(e) => setNewImpact({ ...newImpact, reason: e.target.value })} />
                  </div>
                  <button onClick={addHumanImpact} className="w-fit rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-800 hover:bg-gray-100">
                    + Add impact
                  </button>
                  <input className="input" placeholder="Review comment" value={comment} onChange={(e) => setComment(e.target.value)} />
                  <div className="flex gap-2">
                    <button onClick={() => submitReview(false)} disabled={busy} className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-100">Save review progress</button>
                    <button onClick={() => submitReview(true)} disabled={busy} className="rounded-lg bg-gray-900 px-4 py-1.5 text-xs font-medium text-white hover:bg-gray-700">Complete review</button>
                  </div>
                </div>
              </section>
            </>
          )}
        </div>
      </Card>

      <Card>
        <CardHeader title="Function / Effort / Timeline / Commercial" subtitle="Source is shown — never presented as OIDA-calculated." />
        <div className="grid gap-4 px-4 py-3 md:grid-cols-2">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-gray-400">Functions</div>
            <div className="mt-1 text-sm text-gray-700">
              <span className="text-gray-600">Added {fi?.added?.length || 0} · Modified {fi?.modified?.length || 0} · Removed {fi?.removed?.length || 0} · Unaffected {fi?.unaffected?.length || 0}</span>
            </div>
          </div>
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-gray-400">Effort</div>
            <div className="mt-1 text-sm text-gray-700">
              <span className="font-medium">{ei?.total_md != null ? `${ei.total_md} MD` : ei?.status || "ESTIMATION_REQUIRED"}</span>
              {ei?.source && <span className="ml-1 text-xs text-gray-500">· Source: {ei.source}</span>}
              {(ei?.by_role || []).map((r2, i) => (
                <div key={i} className="text-xs text-gray-600">{r2.role}: {r2.effort} {r2.unit} ({r2.confidence || "—"})</div>
              ))}
            </div>
          </div>
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-gray-400">Timeline</div>
            <div className="mt-1 text-sm text-gray-700">
              <span className="font-medium">{ti?.extension_days != null ? `+${ti.extension_days} working days` : ti?.status || "TBD — PM estimation required"}</span>
              {ti?.source && <span className="ml-1 text-xs text-gray-500">· Source: {ti.source}</span>}
            </div>
          </div>
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-gray-400">Commercial</div>
            <div className="mt-1 text-sm text-gray-700">
              <span className="font-medium">{impact?.commercial_status || "ESTIMATION_REQUIRED"}</span>
              {impact?.pricing_basis && <span className="ml-1 text-xs text-gray-500">· Basis: {impact.pricing_basis}</span>}
              {impact?.approval_evidence?.amount && <div className="text-xs text-gray-600">Approved amount: {impact.approval_evidence.amount}</div>}
              <div className="mt-2 flex gap-2">
                <button onClick={() => approve("APPROVED")} className="rounded-lg border border-gray-300 bg-gray-100 px-3 py-1.5 text-xs font-medium text-gray-900 hover:bg-gray-200">Approve (customer)</button>
                <button onClick={() => approve("REJECTED")} className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50">Reject</button>
              </div>
            </div>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader title="QA / Infra" subtitle="Missing trace is reported honestly — never as zero impact." />
        <div className="grid gap-4 px-4 py-3 md:grid-cols-2">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-gray-400">QA impact</div>
            <div className="mt-1 text-sm text-gray-700">
              New scenarios {qi?.new_scenarios?.length || 0} · Regression {qi?.regression?.length || 0}
              {(!qi || (!qi.new_scenarios?.length && !qi.regression?.length)) && <div className="text-xs text-gray-500">No direct QA impact identified — confidence from trace coverage above.</div>}
            </div>
          </div>
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-gray-400">Infra impact</div>
            <div className="mt-1 text-sm text-gray-700">
              New {ii?.new?.length || 0} · Modified {ii?.modified?.length || 0}
              {(!ii || (!ii.new?.length && !ii.modified?.length)) && <div className="text-xs text-gray-500">No direct infra impact identified — infra is not traced into this project.</div>}
            </div>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader title="History" />
        <div className="px-4 py-3 text-sm text-gray-500">
          Requested {formatDateTime(cr.created_at)} · by {cr.created_by} · Updated {cr.updated_at ? formatDateTime(cr.updated_at) : "—"}
          <div className="mt-1">Scope: unapproved CRs never alter the current baseline. Customer approval is separate from admin technical confirmation.</div>
        </div>
      </Card>
    </div>
  );
}

function SectionHead({ label, note, tone }) {
  const color = { green: "text-emerald-600", amber: "text-amber-600", gray: "text-gray-500", blue: "text-sky-600" }[tone];
  return (
    <div className="mb-1.5 mt-4 flex items-baseline gap-2">
      <span className={`text-xs font-bold uppercase tracking-wide ${color}`}>{label}</span>
      <span className="text-xs text-gray-400">{note}</span>
    </div>
  );
}

function Empty2({ text }) {
  return <div className="rounded-lg border border-dashed border-gray-200 px-3 py-2 text-xs text-gray-400">{text}</div>;
}

function Sum({ label, value }) {
  return (
    <div className="rounded-lg border border-gray-100 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-gray-400">{label}</div>
      <div className="text-sm font-semibold text-gray-800">{value}</div>
    </div>
  );
}

function Muted({ text }) {
  return <div className="text-xs text-gray-400">{text}</div>;
}
