import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { documentApi, pmApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, StatusBadge, Badge, Loading, Empty } from "../components/ui";

const TYPE_LABEL = {
  REQUIREMENT: "Requirement",
  DOCUMENT_SECTION: "Document section",
  PROCESS_FLOW: "Flow",
  PROCESS_STEP: "Flow step",
  ARCHITECTURE_NODE: "Architecture",
  CLARIFICATION: "Clarification",
  ASSUMPTION: "Assumption",
  DECISION: "Decision",
};

function humanRelation(edge, code) {
  const isSource = edge.source === code;
  const target = isSource ? edge.target : edge.source;
  let label;
  if (edge.relation === "DERIVED_FROM") label = isSource ? "Defined In" : "Defines";
  else if (edge.relation === "REFERENCES") label = isSource ? "References" : "Referenced By";
  else label = isSource ? "Links To" : "Linked From";
  return { target, label };
}

export default function RequirementDetail() {
  const { projectId, code } = useParams();
  const { project, pm } = useProjectCtx();
  const [state, setState] = useState(null);

  useEffect(() => {
    if (!projectId || !code) return;
    (async () => {
      const [reqs, graph, ctx, memory, pmTasks] = await Promise.all([
        documentApi.listRequirements(projectId).catch(() => []),
        documentApi.traceGraph(projectId).catch(() => ({ nodes: [], edges: [] })),
        documentApi.semanticContext(projectId, code).catch(() => null),
        documentApi.projectMemory(projectId).catch(() => ({ clarifications: [] })),
        pm && pm.slug ? pmApi.tasks(pm.slug).catch(() => []) : Promise.resolve([]),
      ]);
      const req = (reqs || []).find((r) => r.code === code);
      const nodeById = Object.fromEntries((graph.nodes || []).map((n) => [n.semantic_id, n]));
      const edges = (graph.edges || []).filter((e) => e.source === code || e.target === code);
      const openClarifications = (memory?.clarifications || []).filter((c) => !c.resolved);
      const task = (pmTasks || []).find((t) => (t.title || "").includes(code));
      setState({ req, edges, nodeById, ctx, openClarifications, task });
    })();
  }, [projectId, code, pm?.slug]);

  if (!state) return <Loading />;
  const { req, edges, nodeById, ctx, openClarifications, task } = state;

  return (
    <div className="space-y-4">
      <div>
        <Link to={`/projects/${projectId}/requirements`} className="text-sm text-gray-500 hover:text-gray-800">
          ← Requirement Register
        </Link>
        <div className="mt-2 flex items-center gap-3">
          <h1 className="text-lg font-bold">{code}</h1>
          <span className="text-gray-700">{req?.title}</span>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Requirement" />
          <div className="space-y-2 px-4 py-3 text-sm">
            <Row k="Code" v={<code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs">{code}</code>} />
            <Row k="Title" v={req?.title} />
            <Row k="Source" v={req?.source_type ? `${req.source_type}${req.source_reference ? ` — ${req.source_reference}` : ""}` : "Customer SOW"} />
            <Row k="Status" v={<StatusBadge status={ctx?.status || req?.status} />} />
            <Row k="Current Baseline" v="V2" />
          </div>
        </Card>

        <Card>
          <CardHeader title="Traceability" subtitle="Human relationships, technical ids hidden." />
          <div className="px-4 py-3">
            {edges.length === 0 ? (
              <p className="text-sm text-gray-500">No trace links recorded.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {edges.map((e, i) => {
                  const { target, label } = humanRelation(e, code);
                  const node = nodeById[target];
                  return (
                    <li key={i} className="flex items-start gap-2">
                      <Badge tone="blue">{label}</Badge>
                      <span className="text-gray-700">{node?.display_name || target}</span>
                      {node && (
                        <span className="text-xs text-gray-400">
                          {TYPE_LABEL[node.object_type] || node.object_type}
                        </span>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Planning" subtitle={pm ? "Source: PM Again" : "PM Again not linked"} />
          <div className="px-4 py-3 text-sm">
            {task ? (
              <div className="space-y-2">
                <Row k="Task" v={task.title} />
                <Row k="Status" v={<StatusBadge status={task.status} />} />
                <Row k="Owner" v={task.owner || "Unassigned"} />
                <Row k="Due date" v={task.due_date || "Not Scheduled"} />
              </div>
            ) : (
              <p className="text-gray-500">Not yet materialized as a task.</p>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title="QA" subtitle="Source: QA Again" />
          <div className="px-4 py-3 text-sm">
            <Row k="Included in Validation Scope" v={req ? "Yes" : "—"} />
            <Row k="Status" v={<StatusBadge status="Waiting for test design" />} />
          </div>
        </Card>
      </div>

      {openClarifications.length > 0 && (
        <Card>
          <CardHeader title="Open Clarifications" />
          <ul className="divide-y divide-gray-50 px-4 py-2">
            {openClarifications.map((c) => (
              <li key={c.semantic_id || c.id} className="py-2 text-sm">
                <div className="font-medium text-gray-700">{c.question}</div>
                <div className="text-xs text-gray-400">Unresolved</div>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

function Row({ k, v }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <span className="shrink-0 text-xs font-medium uppercase tracking-wide text-gray-400">{k}</span>
      <span className="text-right text-gray-700">{v}</span>
    </div>
  );
}
