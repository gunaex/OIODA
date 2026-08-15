import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api/client.js";
import { useWorkspace } from "../App.jsx";
import { Card, Empty, Field, inputClass } from "../components/ui.jsx";

/*
 * Traceability explorer over TraceLink truth. Only relationships actually
 * stored are shown — nothing is inferred. Supports search by semantic id,
 * incoming/outgoing links with relation type + revision context, and a
 * radial neighborhood graph.
 */
export function TraceExplorer() {
  const { project, setFocus } = useWorkspace();
  const [graph, setGraph] = useState({ nodes: [], edges: [] });
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState(null);
  const [view, setView] = useState("list");

  useEffect(() => {
    if (project) api.get(`/projects/${project.id}/trace-graph`).then(setGraph).catch(() => {});
  }, [project?.id]);

  const nodeMap = useMemo(() => {
    const m = {};
    graph.nodes.forEach((n) => { m[n.semantic_id] = n; });
    return m;
  }, [graph.nodes]);

  const filtered = graph.nodes.filter((n) => !q || n.semantic_id.toLowerCase().includes(q.toLowerCase()) || (n.display_name || "").toLowerCase().includes(q.toLowerCase()));

  const incoming = graph.edges.filter((e) => e.target === selected);
  const outgoing = graph.edges.filter((e) => e.source === selected);

  return (
    <div className="space-y-4">
      <Card title="Traceability explorer — stored trace links only">
        <div className="mb-3 flex items-center gap-3">
          <input className={inputClass} placeholder="Search semantic ID (e.g. REQ-023, customer_id)…" value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="flex gap-1">
            <button className={`rounded px-2 py-1 text-[12px] ${view === "list" ? "bg-brand-600/20 text-brand-100" : "text-slate-500 hover:bg-surface-2"}`} onClick={() => setView("list")}>List</button>
            <button className={`rounded px-2 py-1 text-[12px] ${view === "graph" ? "bg-brand-600/20 text-brand-100" : "text-slate-500 hover:bg-surface-2"}`} onClick={() => setView("graph")}>Graph</button>
          </div>
        </div>

        {graph.nodes.length === 0 && <Empty>No semantic objects yet. Create requirements, tables, or sections first.</Empty>}

        <div className="grid grid-cols-[280px_1fr] gap-4">
          {/* node list */}
          <div className="max-h-96 space-y-1 overflow-y-auto rounded border border-line p-2">
            {filtered.map((n) => (
              <button
                key={n.semantic_id}
                onClick={() => setSelected(n.semantic_id)}
                className={`block w-full rounded px-2 py-1 text-left text-[12px] ${
                  selected === n.semantic_id ? "bg-brand-600/20 text-brand-100" : "text-slate-300 hover:bg-surface-2"
                }`}
              >
                <span className="font-mono">{n.semantic_id}</span>
                <span className="ml-2 text-slate-500">({n.object_type})</span>
              </button>
            ))}
            {filtered.length === 0 && <p className="p-2 text-[12px] text-slate-500">No matches.</p>}
          </div>

          {/* detail or graph */}
          {view === "list" ? (
            <div className="space-y-3">
              {!selected && <p className="text-[13px] text-slate-500">Select an object to see its incoming and outgoing links.</p>}
              {selected && (
                <>
                  <div className="rounded border border-line bg-surface-2 p-3">
                    <p className="font-mono text-[13px] text-brand-300">{selected}</p>
                    <p className="text-[12px] text-slate-400">{nodeMap[selected]?.object_type} — {nodeMap[selected]?.display_name}</p>
                  </div>
                  <div>
                    <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Incoming ({incoming.length})</p>
                    {incoming.length === 0 && <p className="text-[12px] text-slate-600">none</p>}
                    {incoming.map((e, i) => (
                      <div key={i} className="flex items-center gap-2 border-b border-line/50 py-1 text-[12px]">
                        <button className="font-mono text-slate-200 hover:text-brand-300" onClick={() => setSelected(e.source)}>{e.source}</button>
                        <span className="text-brand-400">—{e.relation}→</span>
                        <span className="font-mono text-slate-200">{e.target}</span>
                        {e.revision_context && <span className="text-slate-500">(rev {e.revision_context})</span>}
                      </div>
                    ))}
                  </div>
                  <div>
                    <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Outgoing ({outgoing.length})</p>
                    {outgoing.length === 0 && <p className="text-[12px] text-slate-600">none</p>}
                    {outgoing.map((e, i) => (
                      <div key={i} className="flex items-center gap-2 border-b border-line/50 py-1 text-[12px]">
                        <span className="font-mono text-slate-200">{e.source}</span>
                        <span className="text-brand-400">—{e.relation}→</span>
                        <button className="font-mono text-slate-200 hover:text-brand-300" onClick={() => setSelected(e.target)}>{e.target}</button>
                        {e.revision_context && <span className="text-slate-500">(rev {e.revision_context})</span>}
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          ) : (
            <NeighborhoodGraph graph={graph} selected={selected} nodeMap={nodeMap} onSelect={setSelected} />
          )}
        </div>
      </Card>
    </div>
  );
}

function NeighborhoodGraph({ graph, selected, nodeMap, onSelect }) {
  const W = 560, H = 360;
  const cx = W / 2, cy = H / 2;

  const neighbors = useMemo(() => {
    if (!selected) return [];
    const set = new Set();
    graph.edges.forEach((e) => {
      if (e.source === selected) set.add(e.target);
      if (e.target === selected) set.add(e.source);
    });
    return [...set];
  }, [graph.edges, selected]);

  if (!selected) return <p className="text-[13px] text-slate-500">Select an object to see its neighborhood.</p>;

  const positions = { [selected]: { x: cx, y: cy } };
  neighbors.forEach((n, i) => {
    const angle = (i / Math.max(neighbors.length, 1)) * Math.PI * 2 - Math.PI / 2;
    positions[n] = { x: cx + Math.cos(angle) * 170, y: cy + Math.sin(angle) * 130 };
  });

  const relevantEdges = graph.edges.filter((e) => e.source === selected || e.target === selected);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-[360px] w-full rounded border border-line bg-surface-0">
      {relevantEdges.map((e, i) => {
        const a = positions[e.source], b = positions[e.target];
        if (!a || !b) return null;
        return (
          <g key={i}>
            <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#4f46e5" strokeWidth="1" />
            <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 4} fill="#94a3b8" fontSize="9" textAnchor="middle">{e.relation}</text>
          </g>
        );
      })}
      {Object.entries(positions).map(([id, p]) => (
        <g key={id} onClick={() => onSelect(id)} style={{ cursor: "pointer" }}>
          <circle cx={p.x} cy={p.y} r={id === selected ? 16 : 12} fill={id === selected ? "#4f46e5" : "#1e2330"} stroke="#6366f1" strokeWidth="1" />
          <text x={p.x} y={p.y - 6} fill="#e2e8f0" fontSize="9" textAnchor="middle">{id.slice(0, 14)}</text>
          <text x={p.x} y={p.y + 6} fill="#94a3b8" fontSize="8" textAnchor="middle">{nodeMap[id]?.object_type || ""}</text>
        </g>
      ))}
    </svg>
  );
}