import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { documentApi, pmApi, qaApi } from "../api";
import { buildOwnerLinks } from "../lib/ownerLinks";
import { useProjectCtx } from "../hooks/useProject";
import {
  Card, CardHeader, StatCard, Badge, StatusBadge,
  Loading, formatDateTime, Table, Tr, Td,
} from "../components/ui";
import {
  Network, GitBranch, ArrowRight, Sparkles, AlertTriangle,
} from "lucide-react";

function documentLinks(projectId, artifacts) {
  const byType = (type) => (artifacts || []).filter((a) => a.type === type);
  const latest = (rows) => (rows.length ? rows[rows.length - 1] : null);
  const ur = byType("UR");
  return [
    {
      title: "Requirement Register",
      type: "register",
      to: `/projects/${projectId}/requirements`,
      version: null,
    },
    {
      title: "UR — True Cloud Migration",
      type: "UR",
      to: `/projects/${projectId}/documents/ur`,
      version: latest(ur)?.revisions?.length ? `v${latest(ur).revisions.length}` : null,
    },
    {
      title: "DR — True Cloud Migration",
      type: "DR",
      to: `/projects/${projectId}/documents/dr`,
      version: null,
    },
    {
      title: "Architecture — Landing Zone",
      type: "architecture",
      to: `/projects/${projectId}/architecture`,
      version: null,
    },
    {
      title: "Migration Flow",
      type: "flow",
      to: `/projects/${projectId}/architecture`,
      version: null,
    },
    {
      title: "Traceability Matrix",
      type: "trace",
      to: `/projects/${projectId}/trace`,
      version: null,
    },
  ];
}

export default function ProjectHome() {
  const { project, pm, qa, baselines, pmAuthed, qaAuthed } = useProjectCtx();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  async function load() {
    setError(null);
    try {
      const projectId = project.id;
      const [requirements, memory, artifacts, timeline, changes, suggestions, truth] = await Promise.all([
        documentApi.listRequirements(projectId),
        documentApi.projectMemory(projectId).catch(() => null),
        documentApi.listArtifacts(projectId).catch(() => []),
        documentApi.timeline(projectId).catch(() => []),
        documentApi.listChanges(projectId).catch(() => []),
        documentApi.listSuggestions(projectId).catch(() => []),
        documentApi.projectTruth(projectId),
      ]);
      const clarifications = (memory?.clarifications || []).filter((c) => !c.resolved);
      const currentBaseline = [...(baselines || [])].sort(
        (a, b) => String(b.name).localeCompare(String(a.name), undefined, { numeric: true })
      )[0];
      setData({
        requirements,
        clarifications,
        artifacts,
        timeline: Array.isArray(timeline) ? timeline.slice(0, 10) : [],
        pendingChanges: (changes || []).filter((c) => c.status !== "CONFIRMED" && c.status !== "CANCELLED"),
        openSuggestions: (suggestions || []).filter((s) => !["ACCEPTED", "REJECTED", "RESOLVED"].includes(s.status)),
        truth,
        currentBaseline,
      });
    } catch (err) {
      setError(err);
    }
  }

  useEffect(() => {
    if (project) load();
  // This read batch is project-scoped. PM/QA context resolving later must not
  // refetch the same truth and Document summaries for the same project.
  }, [project?.id]);

  if (!project) return <Loading />;

  const docs = documentLinks(project.id, data?.artifacts || []);
  const openClarifications = data?.clarifications || [];
  const reqCount = data?.requirements?.length || 0;
  const truth = data?.truth;
  const pmTruth = truth?.pm;
  const qaTruth = truth?.qa;
  const tests = qaTruth?.test_count;
  const pendingChanges = data?.pendingChanges || [];
  const openSuggestions = data?.openSuggestions || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold tracking-tight">{project.name}</h1>
          <StatusBadge status="In Progress" />
        </div>
        <p className="mt-1 text-sm text-gray-500">
          One project. Requirements, documents, plan and QA — in one place.
        </p>
      </div>

      {error && (
        <Card className="px-4 py-3 text-sm text-rose-600">Could not load some live data: {String(error.message || error)}</Card>
      )}

      {/* Delivery workspace binding (R12): honest linked / not-signed-in / not-linked states */}
      <DeliveryWorkspace project={project} pm={pm} qa={qa} pmAuthed={pmAuthed} qaAuthed={qaAuthed} />

      {truth && <ProjectAttention truth={truth} projectId={project.id} />}
      {truth && <ProjectTruth truth={truth} />}

      {/* 10-second owner view */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard label="Current Baseline" value={data?.currentBaseline ? `V${extractVersion(data.currentBaseline.name)}` : "—"} sub={data?.currentBaseline?.name} tone="blue" />
        <StatCard label="Requirements" value={reqCount} sub={`${openClarifications.length} open clarifications`} />
        <StatCard label="Schedule Items" value={pmTruth?.schedule_item_count ?? "—"} sub={truth?.sources?.pm?.source_status || "UNKNOWN"} tone="amber" />
        <StatCard label="Tests" value={tests ?? "—"} sub={truth?.sources?.qa?.source_status || "UNKNOWN"} tone="green" />
      </div>

      {pendingChanges.length > 0 && (
        <Card className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2 text-sm">
            <GitBranch className="h-4 w-4 text-gray-400" />
            <span className="text-gray-700">{pendingChanges.length} pending requirement change{pendingChanges.length === 1 ? "" : "s"} awaiting review</span>
          </div>
          <Link to={`/projects/${project.id}/changes`} className="text-sm font-medium text-gray-900 hover:underline">
            Review <ArrowRight className="inline h-3.5 w-3.5" />
          </Link>
        </Card>
      )}

      {openSuggestions.length > 0 && (
        <Card className="flex items-center justify-between border-violet-200 bg-violet-50 px-4 py-3">
          <div className="flex items-center gap-2 text-sm">
            <Sparkles className="h-4 w-4 text-violet-500" />
            <span className="text-violet-900">{openSuggestions.length} open OIDA suggestion{openSuggestions.length === 1 ? "" : "s"} · {openSuggestions.filter((s) => !s.answer).length} waiting for an answer</span>
          </div>
          <Link to={`/projects/${project.id}/suggestions`} className="text-sm font-medium text-violet-900 hover:underline">
            Review <ArrowRight className="inline h-3.5 w-3.5" />
          </Link>
        </Card>
      )}

      {/* Documents */}
      <Card>
        <CardHeader title="Documents" subtitle="Excel is the working document. Open, download, or view history." />
        <Table head={["Document", "Type", "Status", "Action"]}>
          {docs.map((d) => (
            <Tr key={d.title}>
              <Td className="font-medium text-gray-800">{d.title}</Td>
              <Td><Badge tone="violet">{d.type}</Badge></Td>
              <Td><StatusBadge status={d.type === "DR" ? "Confirmed" : "Current"} /></Td>
              <Td>
                <Link to={d.to} className="inline-flex items-center gap-1 text-sm font-medium text-gray-900 hover:underline">
                  Open
                </Link>
              </Td>
            </Tr>
          ))}
        </Table>
      </Card>

      {/* Recent activity */}
      <Card>
        <CardHeader title="Recent Activity" right={<Link to={`/projects/${project.id}/history`} className="text-xs font-medium text-gray-500 hover:text-gray-800">View history →</Link>} />
        <div className="px-4 py-3">
          {data?.timeline?.length ? (
            <ul className="space-y-2">
              {data.timeline.map((ev, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-gray-300" />
                  <div>
                    <span className="text-gray-700">{ev.label || ev.description || ev.action || ev.event_type || ev.kind || "Activity"}</span>
                    <span className="ml-2 text-xs text-gray-400">{formatDateTime(ev.at || ev.timestamp || ev.created_at)}</span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-gray-500">No recent activity recorded.</p>
          )}
        </div>
      </Card>
    </div>
  );
}

function extractVersion(name) {
  const m = /v?(\d+(?:\.\d+)?)/i.exec(name || "");
  return m ? m[1] : "—";
}

function valueOrState(value, sourceStatus) {
  return value ?? (sourceStatus === "OK" || sourceStatus === "EMPTY" ? "—" : sourceStatus || "UNKNOWN");
}

function ProjectAttention({ truth, projectId }) {
  const attention = truth.attention || { counts: {}, items: [] };
  const pm = truth.pm;
  const qa = truth.qa;
  const infra = truth.infra;
  const pmStatus = truth.sources?.pm?.source_status || "UNKNOWN";
  const qaStatus = truth.sources?.qa?.source_status || "UNKNOWN";
  const infraStatus = truth.sources?.infra?.source_status || "UNKNOWN";
  const milestone = pm?.attention?.next_critical_milestone;
  const effort = pm?.attention?.effort_variance;
  const evidence = qa?.evidence_completeness;
  const ownerLinks = buildOwnerLinks(truth, {
    authContinuity: import.meta.env.VITE_OWNER_AUTH_CONTINUITY === "true",
    pmBase: import.meta.env.VITE_PM_OWNER_URL,
    qaBase: import.meta.env.VITE_QA_OWNER_URL,
  });
  const cards = [
    {
      title: "PM Attention", source: pmStatus, to: `/projects/${projectId}/planning`, link: "Review planning in OIDA", ownerLink: ownerLinks.pm, ownerLabel: "View in PM Again",
      rows: [
        ["Next milestone", milestone ? `${milestone.name || "Milestone"} · ${milestone.status}` : valueOrState(null, pmStatus)],
        ["Slipping delivery", pm ? `${pm.attention?.slipping_item_count ?? 0} overdue` : pmStatus],
        ["Blocked dependencies", pm ? pm.attention?.blocked_dependency_count ?? 0 : pmStatus],
        ["Effort variance", effort?.status ? `${effort.status.replaceAll("_", " ")} · ${effort.remaining_md ?? "—"} MD remaining` : "UNKNOWN"],
      ],
    },
    {
      title: "QA Readiness", source: qaStatus, to: `/projects/${projectId}/qa`, link: "Review QA in OIDA", ownerLink: ownerLinks.qa, ownerLabel: "View in QA Again",
      rows: [
        ["Readiness", valueOrState(qa?.readiness_status, qaStatus)],
        ["Remaining / failed", qa ? `${qa.remaining_test_count ?? 0} / ${qa.failed_test_count ?? 0}` : qaStatus],
        ["Blocking defects", qa ? qa.blocking_defect_count ?? 0 : qaStatus],
        ["Evidence", qa ? `${qa.evidence_status} · ${evidence?.percent ?? "—"}% · TEST ${qa.evidence_classification?.test}` : qaStatus],
      ],
    },
    {
      title: "Infra Readiness", source: infraStatus, to: `/projects/${projectId}/infra-again`, link: "Review Infra in OIDA", ownerLink: ownerLinks.infra, ownerLabel: "View in Infra Again",
      rows: infra ? [
        ["Architecture revision", valueOrState(infra.architecture_revision, infraStatus)],
        ["Feasibility exceptions", infra.feasibility_exception_count ?? "UNKNOWN"],
        ["Environment / connectivity", `${infra.environment_readiness_status} / ${infra.connectivity_exception_count ?? "UNKNOWN"}`],
        ["Implementation / preflight", `${infra.implementation_readiness_status} / ${infra.preflight_status}`],
      ] : [
        ["Architecture revision", infraStatus], ["Environment readiness", infraStatus],
        ["Connectivity", infraStatus], ["Implementation / preflight", infraStatus],
      ],
    },
  ];
  return (
    <Card>
      <CardHeader title="Project Attention" subtitle="Deterministic owner facts · unknown and unbound are never counted as resolved" />
      <div className="grid grid-cols-3 gap-2 border-b px-4 py-3 text-center sm:max-w-md sm:text-left">
        <div><div className="text-lg font-bold text-rose-700">{attention.counts?.blocker ?? 0}</div><div className="text-xs text-gray-500">Blockers</div></div>
        <div><div className="text-lg font-bold text-amber-700">{attention.counts?.issue ?? 0}</div><div className="text-xs text-gray-500">Issues</div></div>
        <div><div className="text-lg font-bold text-gray-700">{attention.counts?.unverified ?? 0}</div><div className="text-xs text-gray-500">Unverified</div></div>
      </div>
      {attention.items?.length > 0 && (
        <ul className="border-b px-4 py-2" aria-label="Prioritized project attention">
          {attention.items.slice(0, 5).map((item) => (
            <li key={item.id} className="flex items-start gap-2 py-1 text-sm text-gray-700">
              <AlertTriangle aria-hidden="true" className={`mt-0.5 h-4 w-4 shrink-0 ${item.priority === "BLOCKER" ? "text-rose-600" : item.priority === "ISSUE" ? "text-amber-600" : "text-gray-400"}`} />
              <span><span className="font-medium">{item.domain} · {item.priority}</span> — {item.title}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="grid gap-3 p-4 lg:grid-cols-3">
        {cards.map((card) => (
          <section key={card.title} className="rounded-lg border border-gray-200 p-3" aria-labelledby={`attention-${card.title.replaceAll(" ", "-").toLowerCase()}`}>
            <div className="flex items-center justify-between gap-2">
              <h2 id={`attention-${card.title.replaceAll(" ", "-").toLowerCase()}`} className="text-sm font-semibold">{card.title}</h2>
              <Badge tone={card.source === "OK" ? "green" : "gray"}>{card.source}</Badge>
            </div>
            <dl className="mt-2 space-y-2">
              {card.rows.map(([label, value]) => <div key={label} className="flex items-start justify-between gap-3 text-xs"><dt className="text-gray-500">{label}</dt><dd className="text-right font-medium text-gray-800">{value}</dd></div>)}
            </dl>
            <Link to={card.to} className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-gray-900 hover:underline">
              {card.link} <ArrowRight size={12} />
            </Link>
            {card.ownerLink ? <a href={card.ownerLink} target="_blank" rel="noreferrer"
              className="ml-3 mt-3 inline-flex items-center gap-1 text-xs font-medium text-gray-900 hover:underline">
              {card.ownerLabel} <ArrowRight size={12} />
            </a> : <span className="ml-3 mt-3 inline-flex text-xs text-gray-400">Owner deep link unavailable</span>}
          </section>
        ))}
      </div>
    </Card>
  );
}

function ProjectTruth({ truth }) {
  const blocks = [
    ["PM Again", truth.pm, truth.sources?.pm, [
      ["Schedule", truth.pm?.schedule_status], ["Milestones", truth.pm?.milestone_count], ["Effort", truth.pm?.effort_status],
    ]],
    ["QA Again", truth.qa, truth.sources?.qa, [
      ["Readiness", truth.qa?.readiness_status], ["Tests", truth.qa?.test_count], ["Blocking defects", truth.qa?.blocking_defect_count],
    ]],
    ["Infra Again", truth.infra, truth.sources?.infra, [
      ["Architecture", truth.infra?.architecture_status], ["Revision", truth.infra?.architecture_revision], ["Environments", truth.infra?.environment_count],
    ]],
  ];
  return (
    <Card>
      <CardHeader title="Cross-service project truth" subtitle={`Contract ${truth.contract_version} · generated ${formatDateTime(truth.generated_at)}`} />
      <div className="grid gap-3 p-4 md:grid-cols-3">
        {blocks.map(([label, domain, source, rows]) => (
          <details key={label} className="rounded-lg border border-gray-200 p-3">
            <summary className="flex cursor-pointer list-none items-center justify-between text-sm font-semibold">
              {label}<Badge tone={source?.source_status === "OK" ? "green" : "amber"}>{source?.source_status || "UNKNOWN"}</Badge>
            </summary>
            {domain ? rows.map(([key, value]) => (
              <div key={key} className="mt-2 flex justify-between text-xs text-gray-600"><span>{key}</span><span>{value ?? "—"}</span></div>
            )) : <p className="mt-2 text-xs text-gray-500">Truth unavailable; no empty values were inferred.</p>}
            <div className="mt-3 border-t pt-2 text-[11px] text-gray-400">
              <div>Binding: {Array.isArray(source?.source_project_id) ? source.source_project_id.join(", ") : source?.source_project_id || "Unbound"}</div>
              <div>Freshness: {source?.freshness || "UNKNOWN"}{source?.age_seconds != null ? ` · ${source.age_seconds}s` : ""}</div>
              <div>Retrieved: {formatDateTime(source?.retrieved_at)}</div>
              {source?.error_message && <div className="mt-1 text-rose-600">{source.error_message}</div>}
            </div>
          </details>
        ))}
      </div>
    </Card>
  );
}

/**
 * R12 — Delivery Workspace binding.
 *
 * Correlation metadata (which PM project and which QA validation scopes
 * operate this Document project) lives on the Document project as
 * `metadata.workspace_bindings`. It is a pointer, never a copy of domain
 * truth — PM/QA remain the bounded authorities for their own data.
 *
 * Honest states:
 *   - not signed in  → "Sign in to PM Again / QA Again" (cannot read live data)
 *   - not linked     → "Not linked" + Initialize button (records bindings)
 *   - linked         → shows the resolved slug + name
 */
function DeliveryWorkspace({ project, pm, qa, pmAuthed, qaAuthed }) {
  const [initializing, setInitializing] = useState(false);
  const [saved, setSaved] = useState(null);
  const [error, setError] = useState(null);
  const [pmCandidates, setPmCandidates] = useState([]);
  const [qaCandidates, setQaCandidates] = useState([]);
  const [selectedPm, setSelectedPm] = useState("");
  const [selectedQa, setSelectedQa] = useState({});

  useEffect(() => {
    if (pmAuthed) pmApi.listProjects().then(setPmCandidates).catch((e) => setError(e.message));
    if (qaAuthed) qaApi.listProjects().then(setQaCandidates).catch((e) => setError(e.message));
  }, [pmAuthed, qaAuthed]);

  const bindings = project?.metadata?.workspace_bindings || {};
  const pmBound = Boolean(bindings.pm_project_slug);
  const qaBoundCount = Object.keys(bindings.qa_project_slugs || {}).length;

  const pmState = !pmAuthed
    ? "signin"
    : pmBound || pm
      ? "linked"
      : "unlinked";
  const qaState = !qaAuthed
    ? "signin"
    : qaBoundCount > 0 || qa.some((q) => q.linked)
      ? "linked"
      : "unlinked";

  async function initialize() {
    setInitializing(true);
    setError(null);
    setSaved(null);
    try {
      const qaBindings = Object.entries(selectedQa).filter(([, id]) => id).map(([scope, id]) => ({
        service: "QA_AGAIN", external_project_id: id, scope_id: scope,
        binding_status: "BOUND", bound_at: new Date().toISOString(), source: "USER_SELECTED",
      }));
      if (!selectedPm && qaBindings.length === 0) {
        setError("Select the exact PM or QA project to bind. OIDA will not infer it from names.");
        return;
      }
      const body = {
        pm_project_slug: selectedPm || undefined,
        qa_project_slugs: Object.fromEntries(qaBindings.map((b) => [b.scope_id, b.external_project_id])),
        binding_contract: {
          contract_version: "project_bindings/v1",
          pm: selectedPm ? { service: "PM_AGAIN", external_project_id: selectedPm, binding_status: "BOUND", bound_at: new Date().toISOString(), source: "USER_SELECTED" } : null,
          qa: qaBindings,
          infra: bindings.infra_design_id ? { service: "INFRA_AGAIN", external_project_id: bindings.infra_design_id, binding_status: "BOUND", source: "LEGACY_POINTER" } : null,
        },
      };
      await documentApi.updateWorkspaceBindings(project.id, body);
      setSaved("Delivery workspace binding saved. Refresh to see the resolved PM/QA links.");
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setInitializing(false);
    }
  }

  return (
    <Card className="px-4 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-gray-800">
          <Network className="h-4 w-4 text-indigo-500" />
          Delivery Workspace
        </div>

        <span className="text-xs text-gray-500">
          PM Again:
          {pmState === "signin" && <Badge tone="amber">Sign in</Badge>}
          {pmState === "linked" && <Badge tone="green">{pm ? pm.name : bindings.pm_project_slug}</Badge>}
          {pmState === "unlinked" && <Badge tone="rose">Not linked</Badge>}
        </span>

        <span className="text-xs text-gray-500">
          QA Again:
          {qaState === "signin" && <Badge tone="amber">Sign in</Badge>}
          {qaState === "linked" && <Badge tone="green">{qaBoundCount || qa.filter((q) => q.linked).length} validation scope(s)</Badge>}
          {qaState === "unlinked" && <Badge tone="rose">Not linked</Badge>}
        </span>

        {pmState === "unlinked" || qaState === "unlinked" ? (
          <button
            onClick={initialize}
            disabled={initializing}
            className="ml-auto rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {initializing ? "Initializing…" : "Initialize Delivery Workspace"}
          </button>
        ) : pmState === "signin" || qaState === "signin" ? (
          <span className="ml-auto text-xs text-amber-600 font-medium">
            Sign in to PM Again / QA Again to link live delivery data
          </span>
        ) : (
          <span className="ml-auto text-xs text-emerald-600 font-medium">Bound</span>
        )}
      </div>

      {saved && <div className="mt-2 text-xs text-emerald-600">{saved}</div>}
      {error && <div className="mt-2 text-xs text-rose-600">{error}</div>}
      {(pmState === "unlinked" || qaState === "unlinked") && (
        <div className="mt-3 grid gap-2 border-t pt-3 md:grid-cols-2">
          {pmState === "unlinked" && <label className="text-xs text-gray-600">Exact PM project
            <select className="input mt-1" value={selectedPm} onChange={(e) => setSelectedPm(e.target.value)}>
              <option value="">Select; do not infer…</option>
              {pmCandidates.map((p) => <option key={p.slug} value={p.slug}>{p.name} · {p.slug}</option>)}
            </select>
          </label>}
          {qaState === "unlinked" && qa.map((scope) => <label key={scope.handoffId} className="text-xs text-gray-600">QA scope {scope.baselineName}
            <select className="input mt-1" value={selectedQa[scope.handoffId] || ""} onChange={(e) => setSelectedQa({ ...selectedQa, [scope.handoffId]: e.target.value })}>
              <option value="">Select; do not infer…</option>
              {qaCandidates.map((p) => <option key={p.slug} value={p.slug}>{p.name} · {p.slug}</option>)}
            </select>
          </label>)}
        </div>
      )}
    </Card>
  );
}
