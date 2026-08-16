import { useEffect, useMemo, useState } from "react";
import { documentApi, infraApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, Badge, Loading } from "../components/ui";
import ArchitectureDiagram from "../components/ArchitectureDiagram";

const VIEWS = [
  { id: "overall", label: "Overall" },
  { id: "track1", label: "Track 1" },
  { id: "track2", label: "Track 2" },
];

function Seg({ options, value, onChange }) {
  return (
    <div className="inline-flex rounded-lg border border-gray-200 bg-white p-0.5 text-xs">
      {options.map((o) => (
        <button
          key={o.id}
          onClick={() => onChange(o.id)}
          className={`rounded-md px-2.5 py-1 font-medium ${value === o.id ? "bg-gray-900 text-white" : "text-gray-600 hover:bg-gray-100"}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function NodeContext({ node, traceMap, reqMap, nameMap }) {
  if (!node) return null;
  const reqCodes = (traceMap[node.semantic_id] || []).filter((c) => c.startsWith("REQ-"));
  const drRefs = (traceMap[node.semantic_id + ":dr"] || []).map((sid) => nameMap[sid] || sid);
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-base font-bold text-gray-900">{node.name}</span>
        <Badge tone="gray">{node.node_type}</Badge>
        {node.environment && <Badge tone="blue">{node.environment}</Badge>}
      </div>
      <div className="mt-1 text-sm text-gray-600">{node.technology}</div>
      <div className="mt-3 grid gap-1.5 text-sm">
        <ContextRow k="Design status" v={<Badge tone="amber">DESIGNED</Badge>} />
        <ContextRow k="Implementation" v={<Badge tone="gray">NOT LINKED</Badge>} />
        <ContextRow
          k="Requirements"
          v={reqCodes.length === 0 ? <span className="text-xs text-gray-400">—</span> : (
            <div className="flex flex-wrap gap-1">
              {reqCodes.map((c) => <span key={c} className="font-mono text-xs text-gray-700">{c} · {reqMap[c] || "—"}</span>)}
            </div>
          )}
        />
        <ContextRow
          k="DR"
          v={drRefs.length === 0 ? <span className="text-xs text-gray-400">—</span> : <span className="text-xs text-gray-700">{drRefs.join(" · ")}</span>}
        />
        <ContextRow
          k="PM"
          v={reqCodes.length === 0 ? <span className="text-xs text-gray-400">—</span> : (
            <span className="text-xs text-gray-700">{reqCodes[0]} — {reqMap[reqCodes[0]] || "—"}</span>
          )}
        />
        <ContextRow k="Infra" v={<span className="text-xs text-gray-500">No realization linked yet</span>} />
        <ContextRow k="QA" v={<span className="text-xs text-gray-500">No infrastructure validation yet</span>} />
      </div>
    </div>
  );
}

function ContextRow({ k, v }) {
  return (
    <div className="flex items-start gap-2">
      <span className="w-24 shrink-0 pt-0.5 text-xs text-gray-500">{k}</span>
      <span className="min-w-0 flex-1">{v}</span>
    </div>
  );
}

export default function InfrastructurePage() {
  const { project, baselines } = useProjectCtx();
  const [arch, setArch] = useState([]);
  const [trace, setTrace] = useState({ nodes: [], edges: [] });
  const [reqs, setReqs] = useState([]);
  const [infra, setInfra] = useState(null);
  const [crs, setCrs] = useState([]);
  const [changes, setChanges] = useState([]);

  const [view, setView] = useState("overall");
  const [detail, setDetail] = useState("HLD");
  const [mode, setMode] = useState("DESIGN");
  const [impactTarget, setImpactTarget] = useState("");
  const [impactData, setImpactData] = useState(null);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (!project) return;
    documentApi.listArchitecture(project.id).then(setArch).catch(() => setArch([]));
    documentApi.traceGraph(project.id).then(setTrace).catch(() => setTrace({ nodes: [], edges: [] }));
    documentApi.listRequirements(project.id).then(setReqs).catch(() => setReqs([]));
    documentApi.listChangeRequests(project.id).then(setCrs).catch(() => setCrs([]));
    documentApi.listChanges(project.id).then(setChanges).catch(() => setChanges([]));
    Promise.allSettled([infraApi.environments(), infraApi.designs()])
      .then(([env, designs]) => setInfra({
        environments: env.status === "fulfilled" ? env.value : null,
        designs: designs.status === "fulfilled" ? designs.value : null,
      }));
  }, [project?.id]);

  const reqMap = useMemo(() => Object.fromEntries(reqs.map((r) => [r.code, r.title])), [reqs]);
  const nameMap = useMemo(() => Object.fromEntries((trace.nodes || []).map((n) => [n.semantic_id, n.display_name])), [trace]);

  const traceMap = useMemo(() => {
    const m = {};
    const dr = {};
    for (const e of trace.edges || []) {
      if (e.target && e.source?.startsWith("REQ-")) (m[e.target] = m[e.target] || []).push(e.source);
      if (e.source && e.target?.startsWith("dr_")) (dr[e.source] = dr[e.source] || []).push(e.target);
    }
    const out = {};
    for (const k of new Set([...Object.keys(m), ...Object.keys(dr)])) out[k] = [...new Set([...(m[k] || []), ...(dr[k] || [])])];
    for (const [k, v] of Object.entries(dr)) out[k + ":dr"] = v;
    return out;
  }, [trace]);

  // Impact target list (CRs + requirement changes).
  const targets = useMemo(() => [
    ...(crs || []).map((c) => ({ id: c.id, code: c.code, kind: "cr", label: `${c.code} — ${c.title || c.requested_change || ""}` })),
    ...(changes || []).map((c) => ({ id: c.id, code: c.code, kind: "change", label: `${c.code} (requirement change)` })),
  ], [crs, changes]);

  useEffect(() => {
    if (mode !== "IMPACT" || !impactTarget) { setImpactData(null); return; }
    const t = targets.find((x) => x.id === impactTarget);
    if (!t) return;
    const p = t.kind === "cr" ? documentApi.getCrImpactAnalysis(t.id) : documentApi.changeImpact(t.id);
    p.then(setImpactData).catch(() => setImpactData(null));
  }, [mode, impactTarget, targets]);

  const filteredDiagrams = useMemo(() => {
    if (view === "track1") return arch.filter((d) => (d.name || "").includes("Track 1"));
    if (view === "track2") return arch.filter((d) => (d.name || "").includes("Track 2"));
    return arch;
  }, [arch, view]);

  const archIds = useMemo(() => {
    const s = new Set();
    for (const d of arch) for (const n of d.nodes || []) if (n.semantic_id) s.add(n.semantic_id);
    return [...s];
  }, [arch]);

  const { nodeStates, highlightPaths, unknownAreas } = useMemo(() => {
    if (mode !== "IMPACT" || !impactTarget) return { nodeStates: {}, highlightPaths: [], unknownAreas: [] };
    const t = targets.find((x) => x.id === impactTarget);
    if (!t) return { nodeStates: {}, highlightPaths: [], unknownAreas: [] };
    const starts = t.kind === "cr" ? (crs.find((c) => c.id === t.id)?.affected_semantic_ids || []) : [t.code];
    const edges = trace.edges || [];

    // BFS over the exact trace graph from the change/CR requirement(s).
    const parent = {};
    const level = {};
    const queue = starts.map((s) => [s, 0]);
    const visited = new Set(starts);
    while (queue.length) {
      const [cur, depth] = queue.shift();
      for (const e of edges) {
        if (e.source === cur && !visited.has(e.target)) {
          visited.add(e.target);
          parent[e.target] = cur;
          level[e.target] = "AFFECTED";
          if (depth < 3) queue.push([e.target, depth + 1]);
        }
      }
    }
    for (const s of starts) {
      for (const e of edges) {
        if (e.target === s && !visited.has(e.source) && !starts.includes(e.source)) {
          visited.add(e.source);
          parent[e.source] = s;
          level[e.source] = "POTENTIAL";
        }
      }
    }

    const states = {};
    const paths = [];
    for (const id of archIds) {
      states[id] = level[id] || "UNAFFECTED";
      if (level[id]) {
        const path = [id];
        let cur = id;
        while (parent[cur] && !starts.includes(parent[cur])) { path.unshift(parent[cur]); cur = parent[cur]; }
        path.unshift(...starts);
        paths.push(path);
      }
    }
    const r = impactData?.result || impactData;
    return { nodeStates: states, highlightPaths: paths, unknownAreas: (r && r.unknown_areas) || [] };
  }, [mode, impactTarget, targets, crs, trace, archIds, impactData]);

  if (!project) return <Loading />;

  const totalComponents = arch.reduce((s, d) => s + (d.nodes?.length || 0), 0);
  const sortedBaselines = [...(baselines || [])].sort((a, b) => String(a.name).localeCompare(String(b.name), undefined, { numeric: true }));
  const currentBaseline = sortedBaselines[sortedBaselines.length - 1];
  const envs = infra?.environments?.environments || [];
  const infraDesigns = (infra?.designs?.designs || []).filter((d) => d.metadata?.name);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-lg font-bold">Infrastructure</h1>
        <p className="text-sm text-gray-500">Design from Document Again · realization state from Infra Again. Click a component for context.</p>
      </div>

      {/* Design vs realization */}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-sky-600">Infrastructure Design</div>
          <div className="mt-1 text-sm font-semibold text-sky-900">AVAILABLE — from current design context</div>
          <div className="text-xs text-sky-700">Baseline {currentBaseline?.name || "—"} · {arch.length} view(s) · {totalComponents} components</div>
        </div>
        <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Infrastructure Realization</div>
          <div className="mt-1 text-sm font-semibold text-gray-800">NOT LINKED YET</div>
          <div className="text-xs text-gray-500">Infra Again has no project/tenant/baseline linkage to “{project.name}”. No deployment state is fabricated.</div>
        </div>
      </div>

      {/* View controls */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-gray-500">Architecture</span>
          <Seg options={VIEWS} value={view} onChange={setView} />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-gray-500">Detail</span>
          <Seg options={[{ id: "HLD", label: "HLD" }, { id: "DETAILED", label: "Detailed" }]} value={detail} onChange={setDetail} />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-gray-500">State</span>
          <Seg options={[{ id: "DESIGN", label: "Design" }, { id: "IMPACT", label: "Impact" }]} value={mode} onChange={setMode} />
        </div>
        {mode === "IMPACT" && (
          <select className="input !w-auto" value={impactTarget} onChange={(e) => setImpactTarget(e.target.value)}>
            <option value="">Select a change / CR…</option>
            {targets.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
          </select>
        )}
      </div>

      {/* Architecture diagram */}
      {filteredDiagrams.length === 0 ? (
        <Card className="px-4 py-8 text-sm text-gray-500">No architecture design exists for this project yet.</Card>
      ) : (
        <ArchitectureDiagram
          diagrams={filteredDiagrams}
          mode={mode}
          nodeStates={nodeStates}
          highlightPaths={highlightPaths}
          onSelect={setSelected}
          selectedId={selected?.semantic_id}
        />
      )}

      {/* Impact legend / unknown areas */}
      {mode === "IMPACT" && (
        <div className="rounded-xl border border-gray-200 bg-white px-4 py-3">
          <div className="flex flex-wrap items-center gap-4 text-xs">
            <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded border-2 border-rose-400 bg-rose-50" /> Affected</span>
            <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded border-2 border-dashed border-amber-400 bg-amber-50" /> Potential</span>
            <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded border border-gray-200 bg-gray-50 opacity-50" /> Unaffected</span>
            {unknownAreas.length > 0 && (
              <span className="flex items-center gap-1.5 text-gray-500">Unknown areas: {unknownAreas.map((u) => u.label).join(" · ")}</span>
            )}
          </div>
        </div>
      )}

      {/* Selected node context */}
      {selected && <NodeContext node={selected} traceMap={traceMap} reqMap={reqMap} nameMap={nameMap} />}

      {/* Design revisions */}
      <Card>
        <CardHeader title="Design Revisions" subtitle="Document Again baselines — the design authority." />
        <div className="flex flex-wrap gap-2 px-4 py-3">
          {sortedBaselines.map((b) => (
            <div key={b.id} className={`rounded-lg border px-3 py-2 text-sm ${b.id === currentBaseline?.id ? "border-emerald-300 bg-emerald-50" : "border-gray-200 bg-white"}`}>
              <div className="font-semibold text-gray-900">{b.name}</div>
              <div className="text-xs text-gray-500">{b.id === currentBaseline?.id ? "current" : "history"}</div>
            </div>
          ))}
          {sortedBaselines.length === 0 && <div className="text-sm text-gray-400">No baselines.</div>}
        </div>
      </Card>

      {/* Infra design workspace (secondary) */}
      <Card>
        <CardHeader title="Infra Design Workspace" subtitle="Infra Again design records — not linked to this project." />
        {!infra?.designs ? <Loading /> : (
          <>
            <div className="flex flex-wrap gap-2 px-4 pb-2">
              {infraDesigns.slice(0, 6).map((d) => (
                <div key={d.designId} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm">
                  <div className="font-medium text-gray-900">{d.metadata?.name || "Untitled Infrastructure Design"}</div>
                  <div className="text-xs text-gray-500">rev {d.revision} · <span className="font-mono">{d.designId}</span> · {d.status}</div>
                </div>
              ))}
              {infraDesigns.length === 0 && <div className="text-sm text-gray-400">No named Infra designs.</div>}
            </div>
            <div className="px-4 pb-3 text-xs text-gray-400">
              {infra?.designs?.count || infraDesigns.length} Infra design records total — shown secondary to the project design.
            </div>
          </>
        )}
      </Card>

      {/* Environments (secondary, compact) */}
      <Card>
        <CardHeader title="Environments" subtitle="Infra Again environment registry (read-only)." />
        {!infra?.environments ? <Loading /> : (
          <div className="flex flex-wrap gap-2 px-4 py-3">
            {envs.map((e) => (
              <div key={e.environmentId} className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm">
                <div className="font-medium text-gray-900">{e.name || "Untitled Environment"}</div>
                <div className="text-xs text-gray-500">{e.classification} · {e.region || "—"}{e.production ? " · production" : ""}</div>
              </div>
            ))}
            {envs.length === 0 && <div className="text-sm text-gray-400">No environments.</div>}
          </div>
        )}
      </Card>
    </div>
  );
}
