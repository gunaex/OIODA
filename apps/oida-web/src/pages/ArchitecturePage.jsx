import { useEffect, useState } from "react";
import { documentApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, Badge, Loading } from "../components/ui";

export default function ArchitecturePage() {
  const { project } = useProjectCtx();
  const [diagrams, setDiagrams] = useState(null);
  const [flows, setFlows] = useState(null);

  useEffect(() => {
    if (!project) return;
    documentApi.listArchitecture(project.id).then(setDiagrams).catch(() => setDiagrams([]));
    documentApi.listFlows(project.id).then(setFlows).catch(() => setFlows([]));
  }, [project?.id]);

  if (!project) return <Loading />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold">Architecture & Process Flows</h1>
        <p className="text-sm text-gray-500">Source: Document Again</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Architecture" />
          <div className="space-y-2 px-4 py-3">
            {(diagrams || []).map((d) => (
              <div key={d.id || d.semantic_id} className="rounded-lg border border-gray-100 p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-gray-800">{d.name}</span>
                  <Badge tone="violet">{d.nodes?.length ?? 0} components</Badge>
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {(d.nodes || []).map((n) => (
                    <span key={n.id || n.semantic_id} className="rounded-md bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                      {n.name}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader title="Process Flows" />
          <div className="space-y-2 px-4 py-3">
            {(flows || []).map((f) => (
              <div key={f.id || f.semantic_id} className="rounded-lg border border-gray-100 p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-gray-800">{f.name}</span>
                  <Badge tone="blue">{f.steps?.length ?? 0} steps</Badge>
                </div>
                <ol className="mt-2 space-y-1">
                  {(f.steps || []).map((s, i) => (
                    <li key={s.id || i} className="flex items-center gap-2 text-xs text-gray-600">
                      <span className="h-5 w-5 shrink-0 rounded-full bg-gray-100 text-center leading-5 text-gray-500">{i + 1}</span>
                      {s.name}
                    </li>
                  ))}
                </ol>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
