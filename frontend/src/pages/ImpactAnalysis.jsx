import React, { useEffect, useMemo, useState } from "react";
import { api } from "../api/client.js";
import { useWorkspace } from "../App.jsx";
import { Card, Empty, Field, inputClass } from "../components/ui.jsx";

/*
 * Deterministic impact analysis over the TraceLink graph. No inferred
 * dependencies: every path shown is an actual stored trace link.
 */
export function ImpactAnalysis() {
  const { project } = useWorkspace();
  const [graph, setGraph] = useState({ nodes: [], edges: [] });
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState("");
  const [depth, setDepth] = useState(2);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (project) api.get(`/projects/${project.id}/trace-graph`).then(setGraph).catch(() => {});
  }, [project?.id]);

  useEffect(() => {
    if (project && selected) {
      api.get(`/projects/${project.id}/impact-analysis/${encodeURIComponent(selected)}?depth=${depth}`)
        .then(setResult).catch(setError);
    } else {
      setResult(null);
    }
  }, [project?.id, selected, depth]);

  const nodes = useMemo(() => graph.nodes.filter((n) => !q || n.semantic_id.toLowerCase().includes(q.toLowerCase())), [graph.nodes, q]);

  return (
    <div className="space-y-4">
      <Card title="Impact analysis V1 — graph/rule based, trace graph is the truth">
        <div className="mb-3 flex items-end gap-3">
          <Field label="Semantic object">
            <input className={inputClass} placeholder="Search and select (e.g. orders.status)" value={q} onChange={(e) => setQ(e.target.value)} />
          </Field>
          <Field label="Max depth">
            <select className={inputClass} value={depth} onChange={(e) => setDepth(Number(e.target.value))}>
              <option value={1}>1 (direct)</option>
              <option value={2}>2</option>
              <option value={3}>3</option>
            </select>
          </Field>
        </div>

        <div className="grid grid-cols-[280px_1fr] gap-4">
          <div className="max-h-96 space-y-1 overflow-y-auto rounded border border-line p-2">
            {nodes.map((n) => (
              <button
                key={n.semantic_id}
                onClick={() => { setSelected(n.semantic_id); setQ(n.semantic_id); }}
                className={`block w-full rounded px-2 py-1 text-left font-mono text-[12px] ${
                  selected === n.semantic_id ? "bg-brand-600/20 text-brand-100" : "text-slate-300 hover:bg-surface-2"
                }`}
              >
                {n.semantic_id} <span className="text-slate-500">({n.object_type})</span>
              </button>
            ))}
            {nodes.length === 0 && <p className="p-2 text-[12px] text-slate-500">No semantic objects yet.</p>}
          </div>

          <div>
            {!result && <Empty>Select an object to analyze impact.</Empty>}
            {result && (
              <div className="space-y-4">
                <Section title="Direct — affected by this (downstream)">
                  {result.direct.downstream.length === 0 && <p className="text-[12px] text-slate-600">none</p>}
                  {result.direct.downstream.map((d, i) => <Row key={i} text={`${d.semantic_id} (${d.relation})`} />)}
                </Section>
                <Section title="Direct — this depends on (upstream)">
                  {result.direct.upstream.length === 0 && <p className="text-[12px] text-slate-600">none</p>}
                  {result.direct.upstream.map((u, i) => <Row key={i} text={`${u.semantic_id} (${u.relation})`} />)}
                </Section>
                <Section title={`Transitive downstream paths (≤ depth ${result.max_depth})`}>
                  {result.paths.downstream.length === 0 && <p className="text-[12px] text-slate-600">none</p>}
                  {result.paths.downstream.map((p, i) => <PathRow key={i} root={result.semantic_id} path={p} />)}
                </Section>
                <Section title={`Transitive upstream paths (≤ depth ${result.max_depth})`}>
                  {result.paths.upstream.length === 0 && <p className="text-[12px] text-slate-600">none</p>}
                  {result.paths.upstream.map((p, i) => <PathRow key={i} root={result.semantic_id} path={p} reverse />)}
                </Section>
              </div>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div>
      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">{title}</p>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

function Row({ text }) {
  return <div className="rounded border border-line bg-surface-2 px-2 py-1 text-[12px] text-slate-300">{text}</div>;
}

function PathRow({ root, path, reverse }) {
  const chain = reverse ? [...path].reverse() : path;
  return (
    <div className="rounded border border-line bg-surface-2 px-2 py-1 font-mono text-[12px] text-slate-300">
      <span className="text-brand-300">{reverse ? chain[0]?.semantic_id || root : root}</span>
      {chain.map((step, i) => (
        <span key={i}>
          <span className="text-slate-500"> —{step.relation}→ </span>
          <span className={reverse ? "text-brand-300" : "text-slate-200"}>{step.semantic_id}</span>
        </span>
      ))}
    </div>
  );
}