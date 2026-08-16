import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Handle, Position } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { api } from "../api/client.js";
import { useWorkspace } from "../App.jsx";
import { applyPositionChanges, DiagramCanvas } from "../components/DiagramCanvas.jsx";
import { Button, Card, Empty, ErrorNote, Field, inputClass } from "../components/ui.jsx";

const STEP_TYPES = ["START", "ACTION", "DECISION", "APPROVAL", "SYSTEM", "MANUAL", "END"];

/*
 * Process flow designer. Canonical source = ProcessFlow / ProcessStep /
 * ProcessTransition. The diagram is a view; node positions are layout only.
 * Steps and flows register stable semantic ids (flow_x, flow_step_x) so
 * TraceLinks and annotations anchor to them.
 */
export function FlowDesigner() {
  const { project, setFocus } = useWorkspace();
  const [flows, setFlows] = useState([]);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState(null);
  const [flowName, setFlowName] = useState("");
  const [stepName, setStepName] = useState("");
  const [stepType, setStepType] = useState("ACTION");
  const [trFrom, setTrFrom] = useState("");
  const [trTo, setTrTo] = useState("");
  const [trLabel, setTrLabel] = useState("");

  const load = useCallback(() => {
    if (project) api.get(`/projects/${project.id}/flows`).then((rows) => {
      setFlows(rows);
      setSelected((prev) => rows.find((f) => f.id === prev?.id) || rows[0] || null);
    }).catch(setError);
  }, [project?.id]);
  useEffect(load, [load]);

  async function createFlow(e) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/flows", { project_id: project.id, name: flowName, semantic_id: `flow_${flowName.toLowerCase().replace(/[^a-z0-9_]/g, "_")}` });
      setFlowName("");
      load();
    } catch (err) { setError(err); }
  }

  async function addStep(e) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/flow-steps", { flow_id: selected.id, name: stepName, step_type: stepType });
      setStepName("");
      load();
    } catch (err) { setError(err); }
  }

  async function addTransition(e) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/flow-transitions", { flow_id: selected.id, from_step_semantic_id: trFrom, to_step_semantic_id: trTo, label: trLabel || null });
      setTrLabel("");
      load();
    } catch (err) { setError(err); }
  }

  async function delStep(s) {
    setError(null);
    try { await api.delete(`/flow-steps/${s.id}`); load(); } catch (err) { setError(err); }
  }

  async function delTransition(t) {
    setError(null);
    try { await api.delete(`/flow-transitions/${t.id}`); load(); } catch (err) { setError(err); }
  }

  return (
    <div className="space-y-4">
      <ErrorNote error={error} />
      <div className="grid grid-cols-[240px_1fr] gap-4">
        <div className="space-y-3">
          <Card title="Flows">
            <ul className="space-y-1">
              {flows.length === 0 && <Empty>No flows.</Empty>}
              {flows.map((f) => (
                <li key={f.id}>
                  <button onClick={() => setSelected(f)} className={`w-full rounded px-2 py-1.5 text-left text-[13px] ${selected?.id === f.id ? "bg-brand-600/20 text-brand-100" : "text-slate-300 hover:bg-surface-2"}`}>{f.name}</button>
                </li>
              ))}
            </ul>
            <form onSubmit={createFlow} className="mt-3 space-y-2 border-t border-line pt-3">
              <Field label="New flow"><input className={inputClass} value={flowName} onChange={(e) => setFlowName(e.target.value)} required /></Field>
              <Button variant="primary" disabled={!flowName}>Create flow</Button>
            </form>
          </Card>
        </div>

        <div className="space-y-4">
          {!selected && <Card title="Flow"><Empty>Select or create a flow.</Empty></Card>}
          {selected && (
            <>
              <FlowDiagram flow={selected} onSave={load} setFocus={setFocus} />
              <div className="grid grid-cols-2 gap-4">
                <Card title={`Steps — ${selected.name}`}>
                  <ul className="space-y-1">
                    {selected.steps.length === 0 && <Empty>No steps.</Empty>}
                    {selected.steps.map((s) => (
                      <li key={s.id} className="flex items-center justify-between rounded border border-line/60 px-2 py-1 text-[12px]">
                        <button className="font-mono text-slate-200 hover:text-brand-300" onClick={() => setFocus(s.semantic_id, s.semantic_id)}>{s.name}</button>
                        <span className="flex items-center gap-2">
                          <span className="text-[10px] uppercase text-slate-500">{s.step_type}</span>
                          <span className="font-mono text-[10px] text-slate-600">{s.semantic_id}</span>
                          <button className="text-slate-500 hover:text-red-400" onClick={() => delStep(s)}>✕</button>
                        </span>
                      </li>
                    ))}
                  </ul>
                  <form onSubmit={addStep} className="mt-3 flex flex-wrap items-end gap-2 border-t border-line pt-3">
                    <Field label="Step name"><input className={inputClass} value={stepName} onChange={(e) => setStepName(e.target.value)} required /></Field>
                    <Field label="Type">
                      <select className={inputClass} value={stepType} onChange={(e) => setStepType(e.target.value)}>
                        {STEP_TYPES.map((t) => <option key={t}>{t}</option>)}
                      </select>
                    </Field>
                    <Button variant="primary" disabled={!stepName}>Add step</Button>
                  </form>
                </Card>

                <Card title="Transitions">
                  <ul className="space-y-1">
                    {selected.transitions.length === 0 && <Empty>No transitions.</Empty>}
                    {selected.transitions.map((t) => (
                      <li key={t.id} className="flex items-center justify-between rounded border border-line/60 px-2 py-1 text-[12px]">
                        <span className="font-mono text-slate-300">{t.from} <span className="text-brand-400">→</span> {t.to}</span>
                        <span className="flex items-center gap-2">
                          {t.label && <span className="text-slate-500">({t.label})</span>}
                          <button className="text-slate-500 hover:text-red-400" onClick={() => delTransition(t)}>✕</button>
                        </span>
                      </li>
                    ))}
                  </ul>
                  <form onSubmit={addTransition} className="mt-3 flex flex-wrap items-end gap-2 border-t border-line pt-3">
                    <Field label="From">
                      <select className={inputClass} value={trFrom} onChange={(e) => setTrFrom(e.target.value)} required>
                        <option value="">select…</option>
                        {selected.steps.map((s) => <option key={s.id} value={s.semantic_id}>{s.name}</option>)}
                      </select>
                    </Field>
                    <Field label="To">
                      <select className={inputClass} value={trTo} onChange={(e) => setTrTo(e.target.value)} required>
                        <option value="">select…</option>
                        {selected.steps.map((s) => <option key={s.id} value={s.semantic_id}>{s.name}</option>)}
                      </select>
                    </Field>
                    <Field label="Label"><input className={inputClass} value={trLabel} onChange={(e) => setTrLabel(e.target.value)} placeholder="Approve" /></Field>
                    <Button variant="primary" disabled={!trFrom || !trTo}>Add</Button>
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

function FlowStepNode({ data }) {
  return (
    <div className="w-40 rounded-md border border-line bg-surface-1 shadow-md">
      <Handle type="target" id={data.semantic_id} position={Position.Left} className="!h-2 !w-2 !border-line !bg-slate-500" />
      <div className="rounded-t-md border-b border-line bg-surface-2 px-2 py-1 text-[12px] font-semibold text-slate-200">{data.name}</div>
      <div className="flex items-center justify-between px-2 py-1 text-[10px]">
        <span className="uppercase text-slate-500">{data.step_type}</span>
        <button className="font-mono text-slate-600 hover:text-brand-300" onClick={() => data.onFocus(data.semantic_id, data.semantic_id)}>{data.semantic_id}</button>
      </div>
      <Handle type="source" id={data.semantic_id} position={Position.Right} className="!h-2 !w-2 !border-line !bg-slate-500" />
    </div>
  );
}

const flowNodeTypes = { flowStep: FlowStepNode };

/* React Flow diagram over the structured flow. */
function FlowDiagram({ flow, onSave, setFocus }) {
  const [pos, setPos] = useState({});

  useEffect(() => {
    const layout = flow.layout || {};
    const next = { ...layout };
    flow.steps.forEach((s, i) => {
      if (!next[s.semantic_id]) next[s.semantic_id] = { x: 40 + (i % 4) * 240, y: 40 + Math.floor(i / 4) * 150 };
    });
    setPos(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flow?.id]);

  const rfNodes = useMemo(
    () => flow.steps.map((s) => ({
      id: s.semantic_id,
      type: "flowStep",
      position: pos[s.semantic_id] || { x: 0, y: 0 },
      data: { name: s.name, step_type: s.step_type, semantic_id: s.semantic_id, onFocus: setFocus },
    })),
    [flow, pos, setFocus]
  );

  const rfEdges = useMemo(
    () => flow.transitions.map((t) => ({
      id: t.id, source: t.from, target: t.to, label: t.label, animated: true,
      markerEnd: { type: "arrowclosed", color: "#6366f1" },
      style: { stroke: "#6366f1" }, labelStyle: { fill: "#94a3b8", fontSize: 9 },
    })),
    [flow]
  );

  function onNodesChange(changes) {
    const { layout, persisted } = applyPositionChanges(changes, pos);
    setPos(layout);
    if (persisted) api.put(`/flows/${flow.id}/layout`, { layout }).catch(() => {});
  }

  return (
    <Card title={`Diagram — ${flow.name}`} actions={<span className="text-[11px] text-slate-500">drag steps; layout is presentation state only</span>}>
      <DiagramCanvas nodes={rfNodes} edges={rfEdges} nodeTypes={flowNodeTypes} onNodesChange={onNodesChange} height={320} />
    </Card>
  );
}