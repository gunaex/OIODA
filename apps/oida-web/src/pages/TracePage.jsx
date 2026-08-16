import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { documentApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, Badge, Loading, Table, Tr, Td } from "../components/ui";

const TYPE_LABEL = {
  REQUIREMENT: "Requirement",
  DOCUMENT_SECTION: "Document",
  PROCESS_FLOW: "Flow",
  PROCESS_STEP: "Flow step",
  ARCHITECTURE_NODE: "Architecture",
  CLARIFICATION: "Clarification",
  ASSUMPTION: "Assumption",
  DECISION: "Decision",
};

function relationLabel(rel) {
  if (rel === "DERIVED_FROM") return "Derived From";
  if (rel === "REFERENCES") return "References";
  return rel;
}

export default function TracePage() {
  const { project } = useProjectCtx();
  const [graph, setGraph] = useState(null);

  useEffect(() => {
    if (project) documentApi.traceGraph(project.id).then(setGraph).catch(() => setGraph({ nodes: [], edges: [] }));
  }, [project?.id]);

  if (!project || !graph) return <Loading />;

  const nodeById = Object.fromEntries((graph.nodes || []).map((n) => [n.semantic_id, n]));
  const requirements = (graph.nodes || []).filter((n) => n.object_type === "REQUIREMENT");
  const covered = new Set(
    (graph.edges || []).flatMap((e) => [e.source, e.target])
  );

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold">Traceability Matrix</h1>
        <p className="text-sm text-gray-500">
          Customer source → requirement → design → baseline → execution → QA → evidence.
        </p>
      </div>

      <Card>
        <CardHeader title="Requirements coverage" subtitle={`${requirements.length} requirements · ${graph.edges?.length ?? 0} trace links`} />
        <Table head={["Requirement", "Defined In", "Status"]}>
          {requirements.map((r) => {
            const out = (graph.edges || []).filter((e) => e.source === r.semantic_id);
            const targets = out.map((e) => {
              const n = nodeById[e.target];
              return `${relationLabel(e.relation)}: ${n?.display_name || e.target}`;
            });
            return (
              <Tr key={r.semantic_id}>
                <Td>
                  <Link to={`/projects/${project.id}/requirements/${r.semantic_id}`} className="font-semibold text-gray-900 hover:underline">
                    {r.semantic_id}
                  </Link>
                  <div className="text-xs text-gray-400">{r.display_name}</div>
                </Td>
                <Td className="text-xs text-gray-600">{targets.length ? targets.join(" · ") : "—"}</Td>
                <Td>{covered.has(r.semantic_id) ? <Badge tone="green">traced</Badge> : <Badge tone="amber">untraced</Badge>}</Td>
              </Tr>
            );
          })}
        </Table>
      </Card>

      <Card>
        <CardHeader title="All trace links" />
        <Table head={["From", "Relation", "To"]}>
          {(graph.edges || []).map((e, i) => (
            <Tr key={i}>
              <Td className="font-medium text-gray-700">{nodeById[e.source]?.display_name || e.source}</Td>
              <Td><Badge tone="blue">{relationLabel(e.relation)}</Badge></Td>
              <Td className="text-gray-700">{nodeById[e.target]?.display_name || e.target}</Td>
            </Tr>
          ))}
        </Table>
      </Card>
    </div>
  );
}
