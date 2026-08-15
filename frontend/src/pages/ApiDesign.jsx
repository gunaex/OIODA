import React, { useCallback, useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useWorkspace } from "../App.jsx";
import { Button, Card, Empty, ErrorNote, Field, inputClass } from "../components/ui.jsx";

const METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"];
const AUTH = ["NONE", "SESSION", "API_KEY", "OAUTH2"];

/*
 * API design workspace over the structured APIEndpoint model. Parameters /
 * request / response / error responses are structured child entities, not
 * buried in free text. Endpoints register semantic ids (api_…) so traces
 * and annotations anchor to them.
 */
export function ApiDesign() {
  const { project, setFocus } = useWorkspace();
  const [endpoints, setEndpoints] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [error, setError] = useState(null);
  const [traces, setTraces] = useState([]);

  // create form
  const [method, setMethod] = useState("POST");
  const [path, setPath] = useState("");
  const [summary, setSummary] = useState("");
  const [auth, setAuth] = useState("NONE");

  // child form
  const [paramName, setParamName] = useState("");
  const [paramLoc, setParamLoc] = useState("query");
  const [reqName, setReqName] = useState("");
  const [reqType, setReqType] = useState("string");
  const [respName, setRespName] = useState("");
  const [respType, setRespType] = useState("string");
  const [errCode, setErrCode] = useState("400");
  const [errMsg, setErrMsg] = useState("");

  // trace form
  const [traceTarget, setTraceTarget] = useState("");
  const [traceRel, setTraceRel] = useState("DERIVED_FROM");

  const load = useCallback(() => {
    if (!project) return;
    api.get(`/projects/${project.id}/api-endpoints`).then((rows) => {
      setEndpoints(rows);
      setSelectedId((prev) => rows.find((e) => e.id === prev)?.id || rows[0]?.id || null);
    }).catch(setError);
    api.get(`/projects/${project.id}/traces`).then(setTraces).catch(() => {});
  }, [project?.id]);
  useEffect(load, [load]);

  const selected = endpoints.find((e) => e.id === selectedId);

  async function createEndpoint(e) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/api-endpoints", { project_id: project.id, method, path, summary: summary || null, authentication: auth });
      setPath(""); setSummary("");
      load();
    } catch (err) { setError(err); }
  }

  async function addChild(kind, payload) {
    setError(null);
    try { await api.post(kind, { endpoint_id: selected.id, ...payload }); load(); } catch (err) { setError(err); }
  }

  async function delChild(kind, id) {
    setError(null);
    try { await api.delete(`/${kind}/${id}`); load(); } catch (err) { setError(err); }
  }

  async function addTrace(e) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/traces", { project_id: project.id, source_semantic_id: traceTarget, target_semantic_id: selected.semantic_id, relation_type: traceRel });
      setTraceTarget("");
      load();
    } catch (err) { setError(err); }
  }

  const endpointTraces = selected ? traces.filter((t) => t.source === selected.semantic_id || t.target === selected.semantic_id) : [];

  return (
    <div className="space-y-4">
      <ErrorNote error={error} />
      <div className="grid grid-cols-[280px_1fr] gap-4">
        <div className="space-y-3">
          <Card title="Endpoints">
            <ul className="space-y-1">
              {endpoints.length === 0 && <Empty>No endpoints.</Empty>}
              {endpoints.map((e) => (
                <li key={e.id}>
                  <button onClick={() => setSelectedId(e.id)} className={`w-full rounded px-2 py-1.5 text-left text-[12px] ${selectedId === e.id ? "bg-brand-600/20 text-brand-100" : "text-slate-300 hover:bg-surface-2"}`}>
                    <span className="font-mono text-[10px] text-slate-500">{e.method}</span> {e.path}
                  </button>
                </li>
              ))}
            </ul>
            <form onSubmit={createEndpoint} className="mt-3 space-y-2 border-t border-line pt-3">
              <div className="flex gap-2">
                <select className={inputClass} value={method} onChange={(e) => setMethod(e.target.value)}>
                  {METHODS.map((m) => <option key={m}>{m}</option>)}
                </select>
                <select className={inputClass} value={auth} onChange={(e) => setAuth(e.target.value)}>
                  {AUTH.map((a) => <option key={a}>{a}</option>)}
                </select>
              </div>
              <Field label="Path"><input className={inputClass} value={path} onChange={(e) => setPath(e.target.value)} placeholder="/purchase-requests/{id}/approve" required /></Field>
              <Field label="Summary"><input className={inputClass} value={summary} onChange={(e) => setSummary(e.target.value)} /></Field>
              <Button variant="primary" disabled={!path}>Create endpoint</Button>
            </form>
          </Card>
        </div>

        <div className="space-y-4">
          {!selected && <Card title="Endpoint"><Empty>Select or create an endpoint.</Empty></Card>}
          {selected && (
            <>
              <Card title={`${selected.method} ${selected.path}`} actions={<button className="font-mono text-[11px] text-slate-500 hover:text-brand-300" onClick={() => setFocus(selected.semantic_id, selected.semantic_id)}>{selected.semantic_id}</button>}>
                <p className="text-[12px] text-slate-400">{selected.summary || "no summary"} · auth: <span className="text-slate-300">{selected.authentication}</span></p>
                {selected.description && <p className="mt-1 text-[12px] text-slate-400">{selected.description}</p>}
              </Card>

              <div className="grid grid-cols-2 gap-4">
                <ChildEditor title="Parameters" rows={selected.parameters.map((p) => ({ ...p, kind: "api-parameters" }))} onDelete={delChild} onAdd={() => addChild("api-parameters", { name: paramName, location: paramLoc, data_type: "string", required: false })}>
                  <Field label="Parameter"><input className={inputClass} value={paramName} onChange={(e) => setParamName(e.target.value)} /></Field>
                  <Field label="Location">
                    <select className={inputClass} value={paramLoc} onChange={(e) => setParamLoc(e.target.value)}>
                      {["query", "path", "header", "body"].map((l) => <option key={l}>{l}</option>)}
                    </select>
                  </Field>
                </ChildEditor>

                <ChildEditor title="Request body fields" rows={selected.request_fields.map((f) => ({ ...f, kind: "api-request-fields" }))} onDelete={delChild} onAdd={() => addChild("api-request-fields", { name: reqName, data_type: reqType, required: false })}>
                  <Field label="Field"><input className={inputClass} value={reqName} onChange={(e) => setReqName(e.target.value)} /></Field>
                  <Field label="Type"><input className={inputClass} value={reqType} onChange={(e) => setReqType(e.target.value)} /></Field>
                </ChildEditor>

                <ChildEditor title="Response fields" rows={selected.response_fields.map((f) => ({ ...f, kind: "api-response-fields" }))} onDelete={delChild} onAdd={() => addChild("api-response-fields", { name: respName, data_type: respType, status_code: "200" })}>
                  <Field label="Field"><input className={inputClass} value={respName} onChange={(e) => setRespName(e.target.value)} /></Field>
                  <Field label="Type"><input className={inputClass} value={respType} onChange={(e) => setRespType(e.target.value)} /></Field>
                </ChildEditor>

                <ChildEditor title="Error responses" rows={selected.error_responses.map((e) => ({ ...e, kind: "api-error-responses" }))} onDelete={delChild} onAdd={() => addChild("api-error-responses", { name: errMsg, status_code: errCode, message: errMsg })}>
                  <Field label="Status"><input className={inputClass} value={errCode} onChange={(e) => setErrCode(e.target.value)} /></Field>
                  <Field label="Message"><input className={inputClass} value={errMsg} onChange={(e) => setErrMsg(e.target.value)} /></Field>
                </ChildEditor>
              </div>

              <Card title="Traceability">
                {endpointTraces.length === 0 && <Empty>No trace links yet.</Empty>}
                <ul className="mb-2 space-y-1">
                  {endpointTraces.map((t) => (
                    <li key={t.id} className="text-[12px] text-slate-300">{t.source} <span className="text-brand-400">—{t.relation}→</span> {t.target}</li>
                  ))}
                </ul>
                <form onSubmit={addTrace} className="flex items-end gap-2 border-t border-line pt-2">
                  <Field label="Link from semantic id">
                    <input className={inputClass} value={traceTarget} onChange={(e) => setTraceTarget(e.target.value)} placeholder="REQ-0001 or DR section" required />
                  </Field>
                  <Field label="Relation">
                    <select className={inputClass} value={traceRel} onChange={(e) => setTraceRel(e.target.value)}>
                      {["DERIVED_FROM", "IMPLEMENTS", "DESIGNED_BY", "VALIDATED_BY", "AFFECTS", "REFERENCES"].map((r) => <option key={r}>{r}</option>)}
                    </select>
                  </Field>
                  <Button variant="primary" disabled={!traceTarget}>Link</Button>
                </form>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function ChildEditor({ title, rows, onAdd, onDelete, children }) {
  const [show, setShow] = useState(false);
  return (
    <Card title={title} actions={<button className="text-[11px] text-brand-300 hover:text-brand-100" onClick={() => setShow((s) => !s)}>+ add</button>}>
      {show && (
        <div className="mb-2 flex flex-wrap items-end gap-2 rounded border border-line bg-surface-2 p-2">
          {children}
          <Button variant="primary" onClick={() => { onAdd(); setShow(false); }}>Add</Button>
        </div>
      )}
      {rows.length === 0 && <Empty>None.</Empty>}
      <ul className="space-y-1">
        {rows.map((r) => (
          <li key={r.id} className="flex items-center justify-between border-b border-line/50 py-1 text-[12px]">
            <span className="font-mono text-slate-200">{r.name}{r.required ? " *" : ""}</span>
            <span className="flex items-center gap-2 text-slate-500">
              {r.data_type && <span>{r.data_type}</span>}
              {r.status_code && <span>{r.status_code}</span>}
              {r.location && <span>{r.location}</span>}
              <button className="text-slate-500 hover:text-red-400" onClick={() => onDelete(r.kind, r.id)}>✕</button>
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}