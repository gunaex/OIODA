import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ReactFlow, Background, Controls, MiniMap, Handle, Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Server, Database, Cloud, Network, Boxes, Link2 } from "lucide-react";
import { documentApi, infraApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, Badge, Loading, Empty, IntegrationState } from "../components/ui";

// Infra Again is the infrastructure authority. OIDA only projects its truth.
const CATEGORY_ICON = {
  STORAGE: Database, DATABASE: Database, COMPUTE: Server, NETWORK: Network,
  APPLICATION: Cloud, INTEGRATION: Link2, SECURITY: Boxes,
};

function categoryColor(category) {
  return {
    STORAGE: "#f59e0b", DATABASE: "#0ea5e9", COMPUTE: "#10b981",
    NETWORK: "#6366f1", APPLICATION: "#8b5cf6", INTEGRATION: "#ec4899",
    SECURITY: "#ef4444",
  }[category] || "#6b7280";
}

function InfraNode({ data }) {
  const Icon = CATEGORY_ICON[data.category] || Cloud;
  return (
    <div className="w-44 rounded-lg border border-gray-200 bg-white px-3 py-2 shadow-sm">
      <Handle type="target" position={Position.Left} />
      <div className="flex items-center gap-2">
        <span className="flex h-6 w-6 items-center justify-center rounded" style={{ background: categoryColor(data.category) + "22", color: categoryColor(data.category) }}>
          <Icon size={14} />
        </span>
        <div className="min-w-0">
          <div className="truncate text-xs font-semibold text-gray-900">{data.label || data.nodeId}</div>
          <div className="text-[10px] text-gray-400">{data.category} · {data.provider} {data.nativeService ? `· ${data.nativeService}` : ""}</div>
        </div>
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

const nodeTypes = { infra: InfraNode };

export default function InfraAgainPage() {
  const { project } = useProjectCtx();
  const [bindings, setBindings] = useState(null);
  const [environments, setEnvironments] = useState([]);
  const [designs, setDesigns] = useState([]);
  const [design, setDesign] = useState(null);      // bound design detail (flow)
  const [selected, setSelected] = useState(null);
  const [linking, setLinking] = useState(false);
  const [linkMsg, setLinkMsg] = useState(null);
  const [error, setError] = useState(null);
  const [loadError, setLoadError] = useState(null);

  const loadBindings = () => documentApi.getWorkspaceBindings(project?.id).then(setBindings).catch(() => setBindings(null));
  const loadInfra = () => {
    setLoadError(null);
    Promise.all([infraApi.environments(), infraApi.designs()])
      .then(([envResult, designResult]) => {
        setEnvironments(Array.isArray(envResult) ? envResult : (envResult?.environments || []));
        setDesigns(Array.isArray(designResult) ? designResult : (designResult?.designs || []));
      })
      .catch((err) => {
        setEnvironments([]);
        setDesigns([]);
        setLoadError(err);
      });
  };

  useEffect(() => { if (project?.id) { loadBindings(); loadInfra(); } }, [project?.id]);

  // Load the bound design's authoritative graph.
  useEffect(() => {
    if (!bindings?.infra_design_id) { setDesign(null); return; }
    infraApi.getDesign(bindings.infra_design_id)
      .then((r) => setDesign(r?.design || r))
      .catch((err) => { setDesign(null); setLoadError(err); });
  }, [bindings?.infra_design_id]);

  async function linkDesign(id) {
    setLinking(true); setLinkMsg(null); setError(null);
    try {
      await documentApi.updateWorkspaceBindings(project.id, { infra_design_id: id });
      setLinkMsg("Infra workspace linked.");
      loadBindings();
    } catch (e) { setError(e.message || String(e)); }
    finally { setLinking(false); }
  }

  const flowNodes = design?.flow?.nodes || [];
  const flowEdges = design?.flow?.edges || [];

  // Build React Flow nodes from authoritative Infra truth.
  const rfNodes = useMemo(() => {
    return flowNodes.map((n, i) => ({
      id: n.nodeId,
      type: "infra",
      position: { x: (i % 4) * 220, y: Math.floor(i / 4) * 140 },
      data: { nodeId: n.nodeId, category: n.category, provider: n.provider, nativeService: n.nativeService, label: n.nativeService || n.nodeId },
    }));
  }, [flowNodes]);
  const rfEdges = useMemo(() => {
    return flowEdges.map((e, i) => ({
      id: e.id || `e${i}`, source: e.source || e.from, target: e.target || e.to, label: e.relation || e.label,
      animated: true,
    }));
  }, [flowEdges]);

  if (!project) return <Loading />;

  const boundDesign = designs.find((d) => d.designId === bindings?.infra_design_id);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold">Infra Workspace</h1>
        <p className="text-sm text-gray-500">Infrastructure authority: Infra Again. OIDA renders only what Infra Again records — nothing is invented.</p>
        <Link
          to={`/projects/${project.id}/council?task=INFRA_REVIEW&q=${encodeURIComponent(`Review the current Infra architecture for the Direct Connect / redundancy requirement. What can be concluded from recorded truth, and what remains unknown?`)}`}
          className="mt-2 inline-block rounded border border-gray-300 px-2 py-1 text-[11px] font-medium text-gray-700 hover:bg-gray-50"
        >
          Review Architecture with Council
        </Link>
      </div>

      {loadError && <IntegrationState service="Infra Again" error={loadError} onRetry={loadInfra} />}

      {/* Binding */}
      <Card className="px-4 py-3">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span className="font-semibold text-gray-700">Infra binding</span>
          {bindings?.infra_design_id ? (
            <Badge tone="green">Bound: {bindings.infra_design_id}{boundDesign ? ` · ${boundDesign.metadata?.name || ""}` : ""}</Badge>
          ) : (
            <Badge tone="amber">Not linked</Badge>
          )}
          <select
            className="input !w-72"
            value={bindings?.infra_design_id || ""}
            onChange={(e) => e.target.value && linkDesign(e.target.value)}
            disabled={linking}
          >
            <option value="">Link a design…</option>
            {designs.map((d) => (
              <option key={d.designId} value={d.designId}>{d.designId}{d.metadata?.name ? ` — ${d.metadata.name}` : ""} ({d.status})</option>
            ))}
          </select>
          {linking && <span className="text-xs text-gray-400">Linking…</span>}
          {linkMsg && <span className="text-xs text-emerald-600">{linkMsg}</span>}
          {error && <span className="text-xs text-rose-600">{error}</span>}
        </div>
        <div className="mt-1 text-[11px] text-gray-400">Correlation pointer only — Infra Again remains the source of truth for components, connections and environments.</div>
      </Card>

      {/* Overview */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Environments" value={environments.length} />
        <Stat label="Designs" value={designs.length} />
        <Stat label="Components" value={flowNodes.length} />
        <Stat label="Connections" value={flowEdges.length} />
      </div>

      {environments.length > 0 && (
        <Card className="px-4 py-3">
          <CardHeader title="Environments" subtitle="From Infra Again." />
          <div className="flex flex-wrap gap-2">
            {environments.map((e) => (
              <span key={e.environmentId} className="rounded border border-gray-200 px-2 py-1 text-xs text-gray-700">
                {e.name} · <span className="text-gray-400">{e.classification}</span>
              </span>
            ))}
          </div>
        </Card>
      )}

      {/* Architecture graph */}
      <Card>
        <CardHeader
          title="Architecture"
          subtitle={design ? `${boundDesign?.designId} · revision ${design.revision} · ${design.status}` : "Link a design to render its authoritative graph."}
        />
        {!design ? (
          <Empty title={bindings?.infra_design_id ? "Design graph unavailable" : "No Infra design linked"} />
        ) : flowNodes.length === 0 ? (
          <Empty title="No architecture components recorded" text="Infra Again has no nodes for this design — the diagram stays empty rather than faking components." />
        ) : (
          <div style={{ height: 420 }} className="border-t border-gray-100">
            <ReactFlow
              nodes={rfNodes}
              edges={rfEdges}
              nodeTypes={nodeTypes}
              fitView
              onNodeClick={(_, n) => setSelected(n.data)}
            >
              <Background />
              <Controls />
              <MiniMap />
            </ReactFlow>
          </div>
        )}
      </Card>

      {/* Node inspector */}
      {selected && (
        <Card className="px-4 py-3">
          <CardHeader title="Component" subtitle="Authority: INFRA_AGAIN" />
          <div className="grid gap-2 text-sm md:grid-cols-2">
            <Row k="Node" v={selected.nodeId} />
            <Row k="Category" v={selected.category} />
            <Row k="Provider" v={selected.provider || "—"} />
            <Row k="Service" v={selected.nativeService || "—"} />
            <Row k="Retrieved" v={new Date().toISOString().slice(0, 19).replace("T", " ")} />
          </div>
        </Card>
      )}

      {flowEdges.length === 0 && design && flowNodes.length > 0 && (
        <Card className="px-4 py-3 text-xs text-amber-600">
          This design records {flowNodes.length} component(s) but no connections — the graph is sparse but truthful. Infra Again has not recorded edges for it.
        </Card>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white px-4 py-3">
      <div className="text-xl font-semibold text-gray-900">{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  );
}

function Row({ k, v }) {
  return (
    <div className="flex gap-2">
      <span className="w-20 shrink-0 text-xs text-gray-400">{k}</span>
      <span className="text-gray-800">{v}</span>
    </div>
  );
}
