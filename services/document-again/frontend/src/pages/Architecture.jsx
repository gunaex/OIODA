import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Background, Controls, MarkerType, ReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { api } from "../api/client.js";
import { useWorkspace } from "../App.jsx";
import { Button, Card, Empty, ErrorNote, Field, inputClass } from "../components/ui.jsx";

const NODE_TYPES = ["USER", "CLIENT", "SERVICE", "DATABASE", "QUEUE", "STORAGE", "EXTERNAL_SYSTEM", "NETWORK_ZONE", "CLOUD_SERVICE"];
const TYPE_COLOR = { DATABASE: "#0ea5e9", SERVICE: "#8b5cf6", CLIENT: "#22c55e", QUEUE: "#f59e0b", STORAGE: "#64748b", EXTERNAL_SYSTEM: "#ef4444", CLOUD_SERVICE: "#14b8a6", NETWORK_ZONE: "#64748b", USER: "#eab308" };

/*
 * Architecture design workspace. Canonical = ArchitectureDiagram/Node/Edge.
 * Nodes are semantic objects (svc_…, db_…) so TraceLinks anchor to them.
 * The diagram is a view; node positions are layout only.
 */
export function Architecture() {
  const { project, setFocus } = useWorkspace();
  const [diagrams, setDiagrams] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [error, setError] = useState(null);
  const [name, setName] = useState("");
  const [nodeName, setNodeName] = useState("");
  const [nodeType, setNodeType] = useState("SERVICE");
  const [nodeTech, setNodeTech] = useState("");
  const [edgeFrom, setEdgeFrom] = useState("");
  const [edgeTo, setEdgeTo] = useState("");
  const [edgeLabel, setEdgeLabel] = useState("");

  const load = useCallback(() => {
    if (project) api.get(`/projects/${project.id}/architecture`).then((rows) => {
      setDiagrams(rows);
      setSelectedId((prev) => rows.find((d) => d.id === prev)?.id || rows[0]?.id || null);
    }).catch(setError);
  }, [project?.id]);
  useEffect(load, [load]);

  const selected = diagrams.find((d) => d.id === selectedId);

  async function createDiagram(e) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/architecture-diagrams", { project_id: project.id, name, semantic_id: `arch_${name.toLowerCase().replace(/[^a-z0-9_]/g, "_")}` });
      setName("");
      load();
    } catch (err) { setError(err); }
  }

  async function addNode(e) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/architecture-nodes", { diagram_id: selected.id, name: nodeName, semantic_id: `svc_${nodeName.toLowerCase().replace(/[^a-z0-9_]/g, "_")}`, node_type: nodeType, technology: nodeTech || null });
      setNodeName(""); setNodeTech("");
      load();
    } catch (err) { setError(err); }
  }

  async function addEdge(e) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/architecture-edges", { diagram_id: selected.id, from_node_semantic_id: edgeFrom, to_node_semantic_id: edgeTo, label: edgeLabel || null });
      setEdgeLabel("");
      load();
    } catch (err) { setError(err); }
  }

  async function delNode(n) { setError(null); try { await api.delete(`/architecture-nodes/${n.id}`); load(); } catch (err) { setError(err); } }
  async function delEdge(e) { setError(null); try { await api.delete(`/architecture-edges/${e.id}`); load(); } catch (err) { setError(err); } }

  return (
    <div className="space-y-4">
      <ErrorNote error={error} />
      <div className="grid grid-cols-[240px_1fr] gap-4">
        <div className="space-y-3">
          <Card title="Diagrams">
            <ul className="space-y-1">
              {diagrams.length === 0 && <Empty>No diagrams.</Empty>}
              {diagrams.map((d) => (
                <li key={d.id}>
                  <button onClick={() => setSelectedId(d.id)} className={`w-full rounded px-2 py-1.5 text-left text-[13px] ${selectedId === d.id ? "bg-brand-600/20 text-brand-100" : "text-slate-300 hover:bg-surface-2"}`}>{d.name}</button>
                </li>
              ))}
            </ul>
            <form onSubmit={createDiagram} className="mt-3 space-y-2 border-t border-line pt-3">
              <Field label="New diagram"><input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} required /></Field>
              <Button variant="primary" disabled={!name}>Create</Button>
            </form>
          </Card>
        </div>

        <div className="space-y-4">
          {!selected && <Card title="Architecture"><Empty>Select or create a diagram.</Empty></Card>}
          {selected && (
            <>
              <ArchDiagram diagram={selected} setFocus={setFocus} />
              <div className="grid grid-cols-2 gap-4">
                <Card title="Nodes">
                  <ul className="space-y-1">
                    {selected.nodes.length === 0 && <Empty>No nodes.</Empty>}
                    {selected.nodes.map((n) => (
                      <li key={n.id} className="flex items-center justify-between rounded border border-line/60 px-2 py-1 text-[12px]">
                        <button className="font-mono text-slate-200 hover:text-brand-300" onClick={() => setFocus(n.semantic_id, n.semantic_id)}>{n.name}</button>
                        <span className="flex items-center gap-2">
                          <span className="rounded px-1 text-[10px]" style={{ background: TYPE_COLOR[n.node_type] + "33", color: TYPE_COLOR[n.node_type] }}>{n.node_type}</span>
                          {n.technology && <span className="text-slate-500">{n.technology}</span>}
                          <button className="text-slate-500 hover:text-red-400" onClick={() => delNode(n)}>✕</button>
                        </span>
                      </li>
                    ))}
                  </ul>
                  <form onSubmit={addNode} className="mt-3 flex flex-wrap items-end gap-2 border-t border-line pt-3">
                    <Field label="Name"><input className={inputClass} value={nodeName} onChange={(e) => setNodeName(e.target.value)} required /></Field>
                    <Field label="Type">
                      <select className={inputClass} value={nodeType} onChange={(e) => setNodeType(e.target.value)}>
                        {NODE_TYPES.map((t) => <option key={t}>{t}</option>)}
                      </select>
                    </Field>
                    <Field label="Technology"><input className={inputClass} value={nodeTech} onChange={(e) => setNodeTech(e.target.value)} placeholder="FastAPI" /></Field>
                    <Button variant="primary" disabled={!nodeName}>Add node</Button>
                  </form>
                </Card>

                <Card title="Edges">
                  <ul className="space-y-1">
                    {selected.edges.length === 0 && <Empty>No edges.</Empty>}
                    {selected.edges.map((e) => (
                      <li key={e.id} className="flex items-center justify-between rounded border border-line/60 px-2 py-1 text-[12px]">
                        <span className="font-mono text-slate-300">{e.from} <span className="text-brand-400">→</span> {e.to}</span>
                        <span className="flex items-center gap-2">
                          {e.label && <span className="text-slate-500">({e.label})</span>}
                          <button className="text-slate-500 hover:text-red-400" onClick={() => delEdge(e)}>✕</button>
                        </span>
                      </li>
                    ))}
                  </ul>
                  <form onSubmit={addEdge} className="mt-3 flex flex-wrap items-end gap-2 border-t border-line pt-3">
                    <Field label="From">
                      <select className={inputClass} value={edgeFrom} onChange={(e) => setEdgeFrom(e.target.value)} required>
                        <option value="">select…</option>
                        {selected.nodes.map((n) => <option key={n.id} value={n.semantic_id}>{n.name}</option>)}
                      </select>
                    </Field>
                    <Field label="To">
                      <select className={inputClass} value={edgeTo} onChange={(e) => setEdgeTo(e.target.value)} required>
                        <option value="">select…</option>
                        {selected.nodes.map((n) => <option key={n.id} value={n.semantic_id}>{n.name}</option>)}
                      </select>
                    </Field>
                    <Field label="Label"><input className={inputClass} value={edgeLabel} onChange={(e) => setEdgeLabel(e.target.value)} placeholder="HTTP" /></Field>
                    <Button variant="primary" disabled={!edgeFrom || !edgeTo}>Add edge</Button>
                  </form>
                </Card>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function ArchNode({ data }) {
  const color = TYPE_COLOR[data.node_type] || "#94a3b8";
  return (
    <div className="w-40 rounded-md border border-line bg-surface-1 shadow-md">
      <div className="rounded-t-md border-b border-line px-2 py-1 text-[12px] font-semibold" style={{ background: color + "22" }}>
        <span className="text-slate-200">{data.name}</span>
      </div>
      <div className="flex items-center justify-between px-2 py-1 text-[10px]">
        <span style={{ color }}>{data.node_type}</span>
        <button className="font-mono text-slate-600 hover:text-brand-300" onClick={() => data.onFocus(data.semantic_id, data.semantic_id)}>{data.semantic_id}</button>
      </div>
    </div>
  );
}

const archNodeTypes = { arch: ArchNode };

function ArchDiagram({ diagram, setFocus }) {
  const [pos, setPos] = useState({});

  useEffect(() => {
    const layout = diagram.layout || {};
    const next = { ...layout };
    diagram.nodes.forEach((n, i) => {
      if (!next[n.semantic_id]) next[n.semantic_id] = { x: 40 + (i % 4) * 220, y: 40 + Math.floor(i / 4) * 150 };
    });
    setPos(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [diagram?.id]);

  const rfNodes = useMemo(
    () => diagram.nodes.map((n) => ({
      id: n.semantic_id,
      type: "arch",
      position: pos[n.semantic_id] || { x: 0, y: 0 },
      data: { name: n.name, node_type: n.node_type, semantic_id: n.semantic_id, onFocus: setFocus },
    })),
    [diagram, pos, setFocus]
  );

  const rfEdges = useMemo(
    () => diagram.edges.map((e) => ({
      id: e.id, source: e.from, target: e.to, label: e.label,
      animated: true, markerEnd: { type: MarkerType.ArrowClosed, color: "#64748b" },
      style: { stroke: "#64748b" }, labelStyle: { fill: "#94a3b8", fontSize: 9 },
    })),
    [diagram]
  );

  function onNodesChange(changes) {
    let persisted = false;
    setPos((prev) => {
      const next = { ...prev };
      for (const c of changes) {
        if (c.type === "position" && c.position) {
          next[c.id] = { x: c.position.x, y: c.position.y };
        }
      }
      return next;
    });
    for (const c of changes) {
      if (c.type === "position" && c.dragging === false) persisted = true;
    }
    if (persisted) {
      api.put(`/architecture-diagrams/${diagram.id}/layout`, { layout: pos }).catch(() => {});
    }
  }

  return (
    <Card title={`Diagram — ${diagram.name}`} actions={<span className="text-[11px] text-slate-500">drag nodes; layout is presentation only</span>}>
      <div className="h-72 overflow-hidden rounded border border-line bg-surface-0">
        <ReactFlow
          nodes={rfNodes}
          edges={rfEdges}
          nodeTypes={archNodeTypes}
          onNodesChange={onNodesChange}
          fitView
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#1e2433" gap={16} />
          <Controls />
        </ReactFlow>
      </div>
    </Card>
  );
}