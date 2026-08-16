import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { documentApi, pmApi, qaApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import {
  Card, CardHeader, StatCard, SectionTitle, Badge, StatusBadge,
  Loading, formatDateTime, Table, Tr, Td,
} from "../components/ui";
import {
  ClipboardList, FileText, Network, GitBranch, CalendarRange, CheckCircle2, ArrowRight, Sparkles,
} from "lucide-react";

function documentLinks(projectId, artifacts) {
  const byType = (type) => (artifacts || []).filter((a) => a.type === type);
  const latest = (rows) => (rows.length ? rows[rows.length - 1] : null);
  const ur = byType("UR");
  const dr = byType("DR");
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
      const [requirements, memory, artifacts, timeline, changes, suggestions, pmData, qaData] = await Promise.all([
        documentApi.listRequirements(projectId),
        documentApi.projectMemory(projectId).catch(() => null),
        documentApi.listArtifacts(projectId).catch(() => []),
        documentApi.timeline(projectId).catch(() => []),
        documentApi.listChanges(projectId).catch(() => []),
        documentApi.listSuggestions(projectId).catch(() => []),
        pm && pm.slug
          ? Promise.all([pmApi.functions(pm.slug).catch(() => []), pmApi.tasks(pm.slug).catch(() => [])])
          : Promise.resolve([[], []]),
        qa && qa.length
          ? qaApi.dashboard(qa[qa.length - 1].slug).catch(() => null)
          : Promise.resolve(null),
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
        functions: pmData[0] || [],
        tasks: pmData[1] || [],
        qaDashboard: qaData,
        currentBaseline,
      });
    } catch (err) {
      setError(err);
    }
  }

  useEffect(() => {
    if (project) load();
  }, [project?.id, pm?.slug, qa?.length]);

  if (!project) return <Loading />;

  const docs = documentLinks(project.id, data?.artifacts || []);
  const openClarifications = data?.clarifications || [];
  const reqCount = data?.requirements?.length || 0;
  const tasks = data?.tasks || [];
  const doneTasks = tasks.filter((t) => t.status === "Done").length;
  const blockedTasks = tasks.filter((t) => t.status === "Blocked").length;
  const currentQa = qa && qa.length ? qa[0] : null;
  const tests = data?.qaDashboard?.activeCycle ? 1 : 0;
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

      {/* 10-second owner view */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard label="Current Baseline" value={data?.currentBaseline ? `V${extractVersion(data.currentBaseline.name)}` : "—"} sub={data?.currentBaseline?.name} tone="blue" />
        <StatCard label="Requirements" value={reqCount} sub={`${openClarifications.length} open clarifications`} />
        <StatCard label="Tasks" value={pmAuthed ? tasks.length : "—"} sub={pmAuthed ? `${doneTasks} done · ${blockedTasks} blocked` : "Sign in to see planning"} tone="amber" />
        <StatCard label="Tests" value={qaAuthed ? tests : "—"} sub={qaAuthed ? (data?.qaDashboard ? "Validation scope ready" : "Awaiting test design") : "Sign in to see QA"} tone="green" />
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

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Execution */}
        <Card>
          <CardHeader title="Execution" subtitle={pmAuthed ? (pm ? "Source: PM Again" : "PM Again not linked") : "Planning data lives in PM Again"} />
          <div className="px-4 py-3">
            {!pmAuthed ? (
              <div className="text-sm text-gray-600">
                <p>Sign in to connect PM Again and see the execution plan (workstreams and tasks).</p>
                <Link to="/login" className="mt-2 inline-flex items-center gap-1 font-medium text-gray-900 hover:underline">
                  Sign in <ArrowRight size={14} />
                </Link>
              </div>
            ) : data?.functions?.length ? (
              <div className="space-y-2">
                {data.functions.map((f) => (
                  <div key={f.id} className="flex items-center justify-between rounded-lg border border-gray-100 px-3 py-2">
                    <span className="text-sm font-medium text-gray-700">{f.name}</span>
                    <StatusBadge status={f.status} />
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500">No workstreams yet.</p>
            )}
            {pmAuthed && (
              <Link to={`/projects/${project.id}/planning`} className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-gray-900 hover:underline">
                Open Planning <ArrowRight size={14} />
              </Link>
            )}
          </div>
        </Card>

        {/* Verification */}
        <Card>
          <CardHeader title="Verification" subtitle={qaAuthed ? (currentQa ? `Baseline ${baselineLabel(currentQa.baselineName)}` : "QA Again not linked") : "QA data lives in QA Again"} />
          <div className="px-4 py-3">
            {!qaAuthed ? (
              <div className="text-sm text-gray-600">
                <p>Sign in to connect QA Again and see the validation scope.</p>
                <Link to="/login" className="mt-2 inline-flex items-center gap-1 font-medium text-gray-900 hover:underline">
                  Sign in <ArrowRight size={14} />
                </Link>
              </div>
            ) : currentQa ? (
              <div className="space-y-2 text-sm text-gray-600">
                <div className="flex justify-between"><span>Validation Scope</span><StatusBadge status={data?.qaDashboard?.activeCycle ? "Ready" : "Received"} /></div>
                <div className="flex justify-between"><span>Test cases</span><span>{data?.qaDashboard?.activeCycle?.testCaseCount ?? 0}</span></div>
                <div className="flex justify-between"><span>Executed</span><span>0 — honest, none run yet</span></div>
              </div>
            ) : (
              <p className="text-sm text-gray-500">No QA validation scope linked.</p>
            )}
            {qaAuthed && (
              <Link to={`/projects/${project.id}/qa`} className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-gray-900 hover:underline">
                Open QA <ArrowRight size={14} />
              </Link>
            )}
          </div>
        </Card>
      </div>

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

function baselineLabel(name) {
  const m = /v?(\d+(?:\.\d+)?)/i.exec(name || "");
  return m ? m[1] : "—";
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
      const body = {};
      if (pmAuthed) {
        const projects = await pmApi.listProjects();
        const match = (projects || []).find(
          (p) => (p.name || "").toLowerCase() === (project.name || "").toLowerCase()
        );
        if (match) body.pm_project_slug = match.slug;
      }
      if (qaAuthed && qa.length > 0) {
        const qaProjects = await qaApi.listProjects();
        const qa_map = {};
        for (const q of qa) {
          const slugified = (q.handoffId || "").toLowerCase().replace(/[^a-z0-9]+/g, "-");
          const fallback = `wp-${slugified}`;
          const found = (qaProjects || []).find((p) => p.slug === q.slug || p.slug === fallback);
          if (found) qa_map[q.handoffId] = found.slug;
        }
        if (Object.keys(qa_map).length > 0) body.qa_project_slugs = qa_map;
      }
      if (Object.keys(body).length === 0) {
        setError("Nothing to bind yet — sign in to PM Again and QA Again first.");
        return;
      }
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
    </Card>
  );
}
