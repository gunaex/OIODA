import { useMemo } from "react";
import {
  ReactFlow, Background, Controls, MiniMap, Handle, Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Cloud, Server, Network, Shield, Layers, Activity, Globe, Lock, Building2, Database,
} from "lucide-react";

/* ------------------------------------------------------------------ *
 * View model (data-driven, NOT project-specific).
 * Semantic architecture nodes -> (provider, domain, icon) -> layout.
 * ------------------------------------------------------------------ */

function providerOf(node) {
  const t = `${node.name || ""} ${node.technology || ""}`.toLowerCase();
  if (/\baws\b|control tower|route 53|cloudwatch|cloudtrail|ec2|vpc|direct connect|mgn|privatelink/.test(t)) return "AWS";
  if (/azure|microsoft/.test(t)) return "Azure";
  if (/gcp|google cloud/.test(t)) return "GCP";
  if (/cyberark/.test(t)) return "CyberArk";
  return null;
}

const DOMAIN_RULES = [
  { id: "operations", label: "Operations", test: (n) => /logging|monitoring|cloudwatch|cloudtrail/i.test(n.name || "") },
  { id: "security", label: "Security Boundary", test: (n) => /firewall|security boundary|cyberark/i.test(n.name || "") },
  { id: "foundation", label: "Foundation Services", test: (n) => /active directory|route 53|\bdns\b|jump host|cyberark/i.test(n.name || "") },
  { id: "connectivity", label: "Connectivity", test: (n) => n.node_type === "NETWORK_ZONE" || /direct connect|connectivity|privatelink|endpoint|subnet|replication path/i.test(n.name || "") },
  { id: "external", label: "External / Enterprise", test: (n) => providerOf(n) === "Azure" || providerOf(n) === "GCP" || /on-prem|premises|data center/i.test(n.name || "") },
  { id: "workloads", label: "Migration & Workloads", test: (n) => /workload|mgn|replication|staging|target/i.test(n.name || "") },
  { id: "aws", label: "AWS Cloud", test: () => true }, // fallback
];

const LANE_ORDER = ["external", "connectivity", "aws", "workloads", "foundation", "security", "operations"];

function domainOf(node) {
  for (const d of DOMAIN_RULES) if (d.test(node)) return d.id;
  return "aws";
}

function iconFor(node, domain) {
  const n = (node.name || "").toLowerCase();
  if (/on-prem|premises|data center/.test(n)) return Building2;
  if (/direct connect/.test(n)) return Network;
  if (/firewall/.test(n)) return Shield;
  if (/cyberark/.test(n)) return Lock;
  if (/dns|route 53/.test(n)) return Globe;
  if (/active directory/.test(n)) return Layers;
  if (/database/.test(n)) return Database;
  if (/logging|monitoring|cloudwatch|cloudtrail/.test(n)) return Activity;
  if (/vpc|landing|legacy|subnet|network/.test(n)) return Network;
  if (/workload|mgn|replication|staging|target|jump host|ec2/.test(n)) return Server;
  const map = { external: Globe, connectivity: Network, aws: Cloud, workloads: Server, foundation: Layers, security: Shield, operations: Activity };
  return map[domain] || Cloud;
}

/* ------------------------------------------------------------------ *
 * Layout
 * ------------------------------------------------------------------ */
const NODE_W = 172;
const NODE_H = 76;
const PAD = 14;
const GROUP_HEADER = 32;
const GROUP_GAP = 40;

function ArchNodeCard({ data }) {
  const { node, provider, icon: Icon, state, selected } = data;
  const ring =
    state === "AFFECTED" ? "border-rose-400 ring-2 ring-rose-300" :
    state === "POTENTIAL" ? "border-amber-400 border-dashed" :
    state === "UNAFFECTED" ? "border-gray-200 opacity-50" :
    selected ? "border-gray-900 ring-1 ring-gray-300" : "border-gray-200";
  return (
    <div className={`relative flex h-full w-full flex-col rounded-lg border bg-white px-2.5 py-2 shadow-sm transition ${ring}`}>
      <Handle type="target" position={Position.Left} className="!h-2 !w-2 !bg-gray-300" />
      <Handle type="source" position={Position.Right} className="!h-2 !w-2 !bg-gray-300" />
      <div className="flex items-start gap-2">
        <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-gray-100 text-gray-600">
          <Icon size={15} />
        </span>
        <div className="min-w-0">
          <div className="line-clamp-2 text-[12px] font-semibold leading-tight text-gray-900">{node.name || "Untitled"}</div>
          {node.technology && <div className="mt-0.5 line-clamp-1 text-[10px] text-gray-500">{node.technology}</div>}
        </div>
      </div>
      <div className="mt-auto flex items-center gap-1.5">
        {provider && <span className="rounded bg-gray-100 px-1 py-0.5 text-[9px] font-semibold text-gray-600">{provider}</span>}
        {state === "AFFECTED" && <span className="rounded bg-rose-100 px-1 py-0.5 text-[9px] font-bold text-rose-700">AFFECTED</span>}
        {state === "POTENTIAL" && <span className="rounded bg-amber-100 px-1 py-0.5 text-[9px] font-bold text-amber-700">POTENTIAL</span>}
      </div>
    </div>
  );
}

function DomainGroup({ data }) {
  const aws = data.label === "AWS Cloud";
  return (
    <div
      className={`h-full w-full rounded-xl border-2 ${aws ? "border-sky-300 bg-sky-50/50" : "border-dashed border-gray-300 bg-gray-50/50"}`}
    >
      <div className={`px-3 pt-2 text-[11px] font-bold uppercase tracking-wide ${aws ? "text-sky-600" : "text-gray-500"}`}>
        {data.label}
        <span className="ml-1 font-normal text-gray-400">{data.count}</span>
      </div>
    </div>
  );
}

function build(diagrams, mode, nodeStates, highlightPaths) {
  // 1. Merge semantic nodes, dedupe by semantic_id.
  const byId = new Map();
  for (const d of diagrams || []) {
    for (const n of d.nodes || []) {
      if (n.semantic_id && !byId.has(n.semantic_id)) byId.set(n.semantic_id, n);
    }
  }

  // 2. Domain grouping.
  const groups = new Map();
  for (const n of byId.values()) {
    const dom = domainOf(n);
    if (!groups.has(dom)) groups.set(dom, []);
    groups.get(dom).push(n);
  }

  // 3. Lane layout.
  const nodes = [];
  const edges = [];
  let x = 0;
  for (const lane of LANE_ORDER) {
    const members = groups.get(lane);
    if (!members || members.length === 0) continue;
    groups.delete(lane);
    const count = members.length;
    const gid = `domain:${lane}`;
    const gw = NODE_W + PAD * 2;
    const gh = GROUP_HEADER + count * (NODE_H + PAD) + PAD;
    nodes.push({
      id: gid, type: "domainGroup", position: { x, y: 0 }, data: { label: DOMAIN_RULES.find((d) => d.id === lane)?.label || lane, count },
      style: { width: gw, height: gh }, draggable: false, selectable: false,
    });
    members.forEach((n, i) => {
      nodes.push({
        id: n.semantic_id,
        type: "archNode",
        parentId: gid,
        extent: "parent",
        position: { x: PAD, y: GROUP_HEADER + i * (NODE_H + PAD) },
        data: { node: n, provider: providerOf(n), icon: iconFor(n, lane), state: nodeStates?.[n.semantic_id], selected: false },
        style: { width: NODE_W, height: NODE_H },
      });
    });
    x += gw + GROUP_GAP;
  }
  // Any uncategorized domain (shouldn't happen) appended at the end.
  for (const [lane, members] of groups) {
    const gid = `domain:${lane}`;
    const count = members.length;
    const gw = NODE_W + PAD * 2;
    const gh = GROUP_HEADER + count * (NODE_H + PAD) + PAD;
    nodes.push({ id: gid, type: "domainGroup", position: { x, y: 0 }, data: { label: lane, count }, style: { width: gw, height: gh }, draggable: false, selectable: false });
    members.forEach((n, i) => nodes.push({ id: n.semantic_id, type: "archNode", parentId: gid, extent: "parent", position: { x: PAD, y: GROUP_HEADER + i * (NODE_H + PAD) }, data: { node: n, provider: providerOf(n), icon: iconFor(n, lane), state: nodeStates?.[n.semantic_id] }, style: { width: NODE_W, height: NODE_H } }));
    x += gw + GROUP_GAP;
  }

  // 4. Edges.
  const pathEdgeSet = new Set();
  for (const p of highlightPaths || []) {
    for (let i = 0; i + 1 < p.length; i++) pathEdgeSet.add(`${p[i]}->${p[i + 1]}`);
  }
  const seen = new Set();
  for (const d of diagrams || []) {
    for (const e of d.edges || []) {
      const s = e.from, t = e.to;
      if (!s || !t || !byId.has(s) || !byId.has(t)) continue;
      const key = `${s}->${t}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const isPath = pathEdgeSet.has(key);
      const dim = mode === "IMPACT" && Object.keys(nodeStates || {}).length > 0 && !isPath;
      edges.push({
        id: `${key}`,
        source: s, target: t,
        type: "smoothstep",
        animated: isPath,
        style: isPath ? { stroke: "#e11d48", strokeWidth: 2.5 } : dim ? { stroke: "#e5e7eb", strokeWidth: 1 } : { stroke: "#9ca3af", strokeWidth: 1.2 },
        label: e.label || undefined,
        labelStyle: { fontSize: 9, fill: "#6b7280" },
      });
    }
  }
  return { nodes, edges };
}

export default function ArchitectureDiagram({ diagrams, mode, nodeStates, highlightPaths, onSelect, selectedId }) {
  const { nodes, edges } = useMemo(
    () => build(diagrams, mode, nodeStates, highlightPaths),
    [diagrams, mode, nodeStates, highlightPaths]
  );
  // Reflect selection onto node data.
  const renderNodes = nodes.map((n) =>
    n.type === "archNode" ? { ...n, data: { ...n.data, selected: n.id === selectedId } } : n
  );

  return (
    <div className="h-[560px] w-full rounded-xl border border-gray-200 bg-white">
      <ReactFlow
        nodes={renderNodes}
        edges={edges}
        nodeTypes={{ archNode: ArchNodeCard, domainGroup: DomainGroup }}
        onNodeClick={(_, node) => { if (node.type === "archNode") onSelect?.(node.data.node); }}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.25}
        maxZoom={2}
        nodesDraggable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={18} size={1} color="#f3f4f6" />
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable className="!bg-gray-50" />
      </ReactFlow>
    </div>
  );
}
