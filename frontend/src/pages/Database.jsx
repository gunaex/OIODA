import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { api } from "../api/client.js";
import { useWorkspace } from "../App.jsx";
import { Button, Card, Empty, ErrorNote, Field, inputClass } from "../components/ui.jsx";

/*
 * Database design workspace — Canonical Model → Diagram View → Document
 * View → Data Dictionary. The structured model is the truth; the ERD is a
 * view over it and node positions are persisted separately from the
 * semantic schema (schema.layout, keyed by semantic id).
 */
export function Database() {
  return (
    <Routes>
      <Route index element={<ModelPage />} />
      <Route path="erd" element={<ErdPage />} />
      <Route path="dictionary" element={<DictionaryPage />} />
    </Routes>
  );
}

const DATA_TYPES = ["VARCHAR", "UUID", "INT", "BIGINT", "DECIMAL", "BOOLEAN", "TIMESTAMP", "TEXT", "JSON", "ENUM"];

function Tabs() {
  return (
    <div className="mb-4 flex gap-1 border-b border-line pb-2 text-[13px]">
      {[
        { to: ".", label: "Schemas / Tables / Fields", end: true },
        { to: "erd", label: "ERD" },
        { to: "dictionary", label: "Data Dictionary" },
      ].map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          end={t.end}
          className={({ isActive }) => (isActive ? "text-brand-300" : "text-slate-500 hover:text-slate-300") + " px-2 py-1"}
        >
          {t.label}
        </NavLink>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Field row — inline editing, semantic id stable                       */
/* ------------------------------------------------------------------ */

function FieldRow({ field, onPatch, onDelete, onFocus }) {
  const [name, setName] = useState(field.name);
  const [dataType, setDataType] = useState(field.data_type);
  const [length, setLength] = useState(field.length ?? "");
  const [def, setDef] = useState(field.default ?? "");
  const [ref, setRef] = useState(field.reference ?? "");
  const [desc, setDesc] = useState(field.description ?? "");

  function commit(patch) {
    onPatch(field.id, patch);
  }

  return (
    <tr className="border-t border-line/60 align-middle">
      <td className="py-1 pr-2">
        <button className="font-mono text-slate-300 hover:text-brand-300" title={field.semantic_id} onClick={() => onFocus(field.semantic_id, field.semantic_id)}>
          {name}{field.primary_key ? " 🔑" : ""}{field.foreign_key ? " 🔗" : ""}
        </button>
      </td>
      <td className="py-1 pr-2">
        <input className="w-28 rounded border border-line bg-surface-0 px-1 py-0.5 text-[12px] text-slate-200" value={name} onChange={(e) => setName(e.target.value)} onBlur={() => name !== field.name && commit({ name })} />
      </td>
      <td className="py-1 pr-2">
        <select className="rounded border border-line bg-surface-0 px-1 py-0.5 text-[12px] text-slate-200" value={dataType} onChange={(e) => { setDataType(e.target.value); commit({ data_type: e.target.value }); }}>
          {DATA_TYPES.map((t) => <option key={t}>{t}</option>)}
        </select>
      </td>
      <td className="py-1 pr-2">
        <input className="w-12 rounded border border-line bg-surface-0 px-1 py-0.5 text-[12px] text-slate-200" value={length} onChange={(e) => setLength(e.target.value)} onBlur={() => commit({ length: length === "" ? null : Number(length) })} />
      </td>
      <td className="py-1 pr-2 text-center">
        <input type="checkbox" checked={!!field.nullable} onChange={(e) => commit({ nullable: e.target.checked })} />
      </td>
      <td className="py-1 pr-2 text-center">
        <input type="checkbox" checked={!!field.primary_key} onChange={(e) => commit({ primary_key: e.target.checked })} />
      </td>
      <td className="py-1 pr-2 text-center">
        <input type="checkbox" checked={!!field.foreign_key} onChange={(e) => commit({ foreign_key: e.target.checked })} />
      </td>
      <td className="py-1 pr-2">
        <input className="w-32 rounded border border-line bg-surface-0 px-1 py-0.5 text-[12px] text-slate-200" value={ref} onChange={(e) => setRef(e.target.value)} onBlur={() => commit({ reference: ref || null })} placeholder="users.id" />
      </td>
      <td className="py-1 pr-2">
        <input className="w-40 rounded border border-line bg-surface-0 px-1 py-0.5 text-[12px] text-slate-300" value={desc} onChange={(e) => setDesc(e.target.value)} onBlur={() => commit({ description: desc || null })} />
      </td>
      <td className="py-1 text-right">
        <button className="text-[12px] text-slate-500 hover:text-red-400" onClick={() => onDelete(field)}>✕</button>
      </td>
    </tr>
  );
}

/* ------------------------------------------------------------------ */
/* Model page — tables + fields + relations                            */
/* ------------------------------------------------------------------ */

function ModelPage() {
  const { project, setFocus } = useWorkspace();
  const [schemas, setSchemas] = useState([]);
  const [error, setError] = useState(null);
  const [schemaName, setSchemaName] = useState("");
  const [tableName, setTableName] = useState("");
  const [activeTableId, setActiveTableId] = useState(null);

  // relation form
  const [relFrom, setRelFrom] = useState("");
  const [relTo, setRelTo] = useState("");
  const [relType, setRelType] = useState("MANY_TO_ONE");

  const load = useCallback(() => {
    if (project) api.get(`/projects/${project.id}/db-schemas`).then(setSchemas).catch(setError);
  }, [project?.id]);
  useEffect(load, [load]);

  const schema = schemas[0];
  const activeTable = schema?.tables.find((t) => t.id === activeTableId);

  const allFields = useMemo(() => {
    const out = [];
    (schema?.tables || []).forEach((t) => t.fields.forEach((f) => out.push({ ...f, table: t.name, table_semantic_id: t.semantic_id })));
    return out;
  }, [schema]);

  async function createSchema(e) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/db-schemas", { project_id: project.id, name: schemaName, semantic_id: `sch_${schemaName.toLowerCase().replace(/[^a-z0-9_]/g, "_")}` });
      setSchemaName("");
      load();
    } catch (err) { setError(err); }
  }

  async function createTable(e) {
    e.preventDefault();
    setError(null);
    try {
      const created = await api.post("/db-tables", { schema_id: schema.id, name: tableName });
      setTableName("");
      setActiveTableId(created.id);
      load();
    } catch (err) { setError(err); }
  }

  async function renameTable(name) {
    setError(null);
    try { await api.patch(`/db-tables/${activeTable.id}`, { name }); load(); } catch (err) { setError(err); }
  }

  async function deleteTable() {
    setError(null);
    if (!confirm(`Delete table ${activeTable.name} and its fields?`)) return;
    try { await api.delete(`/db-tables/${activeTable.id}`); setActiveTableId(null); load(); } catch (err) { setError(err); }
  }

  async function addField(field) {
    setError(null);
    try { await api.post("/db-fields", field); load(); } catch (err) { setError(err); }
  }

  async function patchField(fieldId, patch) {
    setError(null);
    try { await api.patch(`/db-fields/${fieldId}`, patch); load(); } catch (err) { setError(err); }
  }

  async function deleteField(field) {
    setError(null);
    try { await api.delete(`/db-fields/${field.id}`); load(); } catch (err) { setError(err); }
  }

  async function createRelation(e) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/db-relations", { schema_id: schema.id, from_field_semantic_id: relFrom, to_field_semantic_id: relTo, relation_type: relType });
      setRelFrom(""); setRelTo("");
      load();
    } catch (err) { setError(err); }
  }

  async function deleteRelation(rel) {
    setError(null);
    try { await api.delete(`/db-relations/${rel.id}`); load(); } catch (err) { setError(err); }
  }

  return (
    <div className="space-y-4">
      <Tabs />
      <ErrorNote error={error} />

      {!schema && (
        <Card title="Create database schema">
          <form onSubmit={createSchema} className="flex items-end gap-3">
            <Field label="Schema name"><input className={inputClass} value={schemaName} onChange={(e) => setSchemaName(e.target.value)} required /></Field>
            <Button variant="primary">Create</Button>
          </form>
        </Card>
      )}

      {schema && (
        <div className="grid grid-cols-[240px_1fr] gap-4">
          {/* Tables list */}
          <div className="space-y-2">
            <Card title="Tables">
              <ul className="space-y-1">
                {schema.tables.length === 0 && <Empty>No tables.</Empty>}
                {schema.tables.map((t) => (
                  <li key={t.id}>
                    <button
                      onClick={() => setActiveTableId(t.id)}
                      className={`flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-[13px] ${
                        activeTableId === t.id ? "bg-brand-600/20 text-brand-100" : "text-slate-300 hover:bg-surface-2"
                      }`}
                    >
                      <span>{t.name}</span>
                      <span className="text-[10px] text-slate-600">{t.fields.length}</span>
                    </button>
                  </li>
                ))}
              </ul>
              <form onSubmit={createTable} className="mt-3 space-y-2 border-t border-line pt-3">
                <Field label="New table">
                  <input className={inputClass} value={tableName} onChange={(e) => setTableName(e.target.value)} required />
                </Field>
                <Button variant="primary" disabled={!tableName}>Add table</Button>
              </form>
            </Card>
          </div>

          {/* Table detail + relations */}
          <div className="space-y-4">
            {!activeTable && <Card title="Table detail"><Empty>Select a table to inspect and edit its fields.</Empty></Card>}

            {activeTable && (
              <Card
                title={`${activeTable.name} — fields`}
                actions={
                  <>
                    <input
                      className={`${inputClass} w-44`}
                      defaultValue={activeTable.name}
                      onBlur={(e) => e.target.value !== activeTable.name && renameTable(e.target.value)}
                    />
                    <button className="text-[12px] text-red-400 hover:text-red-300" onClick={deleteTable}>delete table</button>
                  </>
                }
              >
                <p className="mb-2 font-mono text-[11px] text-slate-500">{activeTable.semantic_id}</p>
                <table className="w-full text-[12px]">
                  <thead>
                    <tr className="text-left text-[10px] uppercase tracking-wider text-slate-500">
                      <th className="pb-1">Field</th><th>Name</th><th>Type</th><th>Len</th><th>Null</th><th>PK</th><th>FK</th><th>Reference</th><th>Description</th><th />
                    </tr>
                  </thead>
                  <tbody>
                    {activeTable.fields.length === 0 && <tr><td colSpan={10} className="py-2 text-slate-500">No fields yet.</td></tr>}
                    {activeTable.fields.map((f) => (
                      <FieldRow key={f.id} field={f} onPatch={patchField} onDelete={deleteField} onFocus={setFocus} />
                    ))}
                  </tbody>
                </table>

                <AddFieldForm onAdd={addField} table={activeTable} />
              </Card>
            )}

            {schema && (
              <Card title="Relations">
                {schema.relations.length === 0 && <Empty>No relations yet.</Empty>}
                <ul className="space-y-1">
                  {schema.relations.map((r) => (
                    <li key={r.id} className="flex items-center justify-between rounded border border-line/60 px-2 py-1 text-[12px]">
                      <span className="font-mono text-slate-300">{r.from} <span className="text-brand-400">→{r.relation_type}→</span> {r.to}</span>
                      <button className="text-slate-500 hover:text-red-400" onClick={() => deleteRelation(r)}>✕</button>
                    </li>
                  ))}
                </ul>
                <form onSubmit={createRelation} className="mt-3 flex flex-wrap items-end gap-2 border-t border-line pt-3">
                  <Field label="From field">
                    <select className={inputClass} value={relFrom} onChange={(e) => setRelFrom(e.target.value)} required>
                      <option value="">select…</option>
                      {allFields.map((f) => <option key={f.semantic_id} value={f.semantic_id}>{f.table}.{f.name}</option>)}
                    </select>
                  </Field>
                  <Field label="To field">
                    <select className={inputClass} value={relTo} onChange={(e) => setRelTo(e.target.value)} required>
                      <option value="">select…</option>
                      {allFields.map((f) => <option key={f.semantic_id} value={f.semantic_id}>{f.table}.{f.name}</option>)}
                    </select>
                  </Field>
                  <Field label="Type">
                    <select className={inputClass} value={relType} onChange={(e) => setRelType(e.target.value)}>
                      {["MANY_TO_ONE", "ONE_TO_MANY", "ONE_TO_ONE", "MANY_TO_MANY"].map((t) => <option key={t}>{t}</option>)}
                    </select>
                  </Field>
                  <Button variant="primary" disabled={!relFrom || !relTo}>Add relation</Button>
                </form>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function AddFieldForm({ table, onAdd }) {
  const [name, setName] = useState("");
  const [dataType, setDataType] = useState("VARCHAR");
  const [pk, setPk] = useState(false);
  const [fk, setFk] = useState(false);
  const [nullable, setNullable] = useState(false);
  const [ref, setRef] = useState("");
  const [desc, setDesc] = useState("");

  function submit(e) {
    e.preventDefault();
    onAdd({
      table_id: table.id, name, data_type: dataType, primary_key: pk, foreign_key: fk,
      nullable, reference: ref || null, description: desc || null,
    });
    setName(""); setRef(""); setDesc(""); setPk(false); setFk(false); setNullable(false);
  }

  return (
    <form onSubmit={submit} className="mt-3 flex flex-wrap items-end gap-2 border-t border-line pt-3">
      <Field label="Field name"><input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} required /></Field>
      <Field label="Type">
        <select className={inputClass} value={dataType} onChange={(e) => setDataType(e.target.value)}>
          {DATA_TYPES.map((t) => <option key={t}>{t}</option>)}
        </select>
      </Field>
      <label className="flex items-center gap-1 pb-1.5 text-[12px] text-slate-400"><input type="checkbox" checked={pk} onChange={(e) => setPk(e.target.checked)} /> PK</label>
      <label className="flex items-center gap-1 pb-1.5 text-[12px] text-slate-400"><input type="checkbox" checked={fk} onChange={(e) => setFk(e.target.checked)} /> FK</label>
      <label className="flex items-center gap-1 pb-1.5 text-[12px] text-slate-400"><input type="checkbox" checked={nullable} onChange={(e) => setNullable(e.target.checked)} /> Null</label>
      {fk && <Field label="Reference"><input className={inputClass} value={ref} onChange={(e) => setRef(e.target.value)} placeholder="users.id" /></Field>}
      <Field label="Description"><input className={inputClass} value={desc} onChange={(e) => setDesc(e.target.value)} /></Field>
      <Button variant="primary" disabled={!name}>Add field</Button>
    </form>
  );
}

/* ------------------------------------------------------------------ */
/* ERD page — draggable nodes over structured truth                     */
/* ------------------------------------------------------------------ */

function ErdPage() {
  const { project, setFocus } = useWorkspace();
  const [schemas, setSchemas] = useState([]);
  const [pos, setPos] = useState({});
  const [error, setError] = useState(null);
  const posRef = useRef({});

  const schema = schemas[0];

  const load = useCallback(() => {
    if (project) api.get(`/projects/${project.id}/db-schemas`).then(setSchemas).catch(setError);
  }, [project?.id]);
  useEffect(load, [load]);

  useEffect(() => { posRef.current = pos; }, [pos]);

  // initialize / reconcile positions
  useEffect(() => {
    if (!schema) return;
    const layout = schema.layout || {};
    const next = { ...layout };
    schema.tables.forEach((t, i) => {
      if (!next[t.semantic_id]) next[t.semantic_id] = { x: 40 + (i % 3) * 260, y: 40 + Math.floor(i / 3) * 220 };
    });
    setPos(next);
    posRef.current = next;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [schema?.id]);

  const fieldTable = useMemo(() => {
    const map = {};
    (schema?.tables || []).forEach((t) => t.fields.forEach((f) => { map[f.semantic_id] = t.semantic_id; }));
    return map;
  }, [schema]);

  function onPointerDown(e, id) {
    e.preventDefault();
    const p = posRef.current[id] || { x: 0, y: 0 };
    const start = { id, startX: e.clientX, startY: e.clientY, origX: p.x, origY: p.y };
    const move = (ev) => {
      const next = { ...posRef.current, [id]: { x: start.origX + (ev.clientX - start.startX), y: start.origY + (ev.clientY - start.startY) } };
      posRef.current = next;
      setPos(next);
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      api.put(`/db-schemas/${schema.id}/erd-layout`, { layout: posRef.current }).catch(setError);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  if (!schema) return <div className="space-y-4"><Tabs /><Empty>Create a schema first.</Empty></div>;

  return (
    <div className="space-y-4">
      <Tabs />
      <ErrorNote error={error} />
      <p className="text-[12px] text-slate-500">
        ERD is a view over the structured model. Drag nodes to arrange them — positions are stored separately and never change semantic identity.
      </p>
      <div className="relative h-[560px] overflow-hidden rounded-lg border border-line bg-surface-0">
        <svg className="pointer-events-none absolute inset-0 h-full w-full">
          {schema.relations.map((r) => {
            const a = fieldTable[r.from];
            const b = fieldTable[r.to];
            if (!a || !b || !pos[a] || !pos[b]) return null;
            const x1 = pos[a].x + 104, y1 = pos[a].y + 70;
            const x2 = pos[b].x + 104, y2 = pos[b].y + 70;
            const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
            return (
              <g key={r.id}>
                <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#6366f1" strokeWidth="1.5" markerEnd="url(#arrow)" />
                <text x={mx} y={my - 4} fill="#94a3b8" fontSize="10" textAnchor="middle">{r.relation_type}</text>
              </g>
            );
          })}
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#6366f1" />
            </marker>
          </defs>
        </svg>

        {schema.tables.map((t) => {
          const p = pos[t.semantic_id] || { x: 0, y: 0 };
          return (
            <div
              key={t.id}
              className="absolute w-52 cursor-move rounded-md border border-line bg-surface-1 shadow-md"
              style={{ left: p.x, top: p.y, touchAction: "none" }}
              onPointerDown={(e) => onPointerDown(e, t.semantic_id)}
            >
              <div className="rounded-t-md border-b border-line bg-surface-2 px-2 py-1.5 text-[13px] font-semibold text-slate-200">
                {t.name}
              </div>
              <div className="p-1.5">
                {t.fields.map((f) => (
                  <div key={f.id} className="flex items-center justify-between px-1 py-0.5 text-[11px]">
                    <button className="font-mono text-slate-300 hover:text-brand-300" onClick={(e) => { e.stopPropagation(); setFocus(f.semantic_id, f.semantic_id); }}>
                      {f.name}{f.primary_key ? " 🔑" : ""}{f.foreign_key ? " 🔗" : ""}
                    </button>
                    <span className="text-slate-500">{f.data_type}</span>
                  </div>
                ))}
                {t.fields.length === 0 && <p className="px-1 py-1 text-[11px] text-slate-600">no fields</p>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Data dictionary                                                     */
/* ------------------------------------------------------------------ */

function DictionaryPage() {
  const { project, setFocus } = useWorkspace();
  const [schemas, setSchemas] = useState([]);
  const [dictionary, setDictionary] = useState([]);
  const [q, setQ] = useState("");
  const [tableFilter, setTableFilter] = useState("");
  const schema = schemas[0];

  useEffect(() => {
    if (project) api.get(`/projects/${project.id}/db-schemas`).then(setSchemas).catch(() => {});
  }, [project?.id]);
  useEffect(() => {
    if (schema) api.get(`/db-schemas/${schema.id}/data-dictionary`).then(setDictionary).catch(() => {});
  }, [schema?.id]);

  const tables = useMemo(() => [...new Set(dictionary.map((r) => r.table))].sort(), [dictionary]);
  const rows = dictionary.filter((r) => {
    if (tableFilter && r.table !== tableFilter) return false;
    if (q) {
      const hay = `${r.table} ${r.field} ${r.data_type} ${r.reference || ""} ${r.description || ""} ${r.field_semantic_id}`.toLowerCase();
      if (!hay.includes(q.toLowerCase())) return false;
    }
    return true;
  });

  return (
    <div className="space-y-4">
      <Tabs />
      <Card title="Data Dictionary — generated view over the canonical model (never edited directly)">
        {!schema && <Empty>No schema yet.</Empty>}
        {schema && (
          <>
            <div className="mb-3 flex gap-2">
              <input className={inputClass} placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} />
              <select className={inputClass} value={tableFilter} onChange={(e) => setTableFilter(e.target.value)}>
                <option value="">all tables</option>
                {tables.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
              <Button onClick={() => exportDictionary(rows)}>Export (copy JSON)</Button>
            </div>
            <table className="w-full text-[12px]">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wider text-slate-500">
                  <th className="pb-2">Table</th><th className="pb-2">Field</th><th className="pb-2">Type</th><th className="pb-2">Len</th>
                  <th className="pb-2">Null</th><th className="pb-2">Key</th><th className="pb-2">Default</th><th className="pb-2">Reference</th>
                  <th className="pb-2">Description</th><th className="pb-2">Semantic ID</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 && <tr><td colSpan={10} className="py-2 text-slate-500">No matching rows.</td></tr>}
                {rows.map((row) => (
                  <tr key={row.field_semantic_id} className="border-t border-line/50">
                    <td className="py-1 text-slate-300">{row.table}</td>
                    <td className="py-1">
                      <button className="font-mono text-slate-200 hover:text-brand-300" onClick={() => setFocus(row.field_semantic_id, row.field_semantic_id)}>{row.field}</button>
                    </td>
                    <td className="py-1 text-slate-500">{row.data_type}</td>
                    <td className="py-1 text-slate-500">{row.length ?? ""}</td>
                    <td className="py-1 text-slate-500">{row.nullable ? "Y" : "N"}</td>
                    <td className="py-1 text-slate-500">{row.primary_key ? "PK" : row.foreign_key ? "FK" : ""}</td>
                    <td className="py-1 text-slate-500">{row.default ?? ""}</td>
                    <td className="py-1 text-slate-500">{row.reference || ""}</td>
                    <td className="py-1 text-slate-400">{row.description || ""}</td>
                    <td className="py-1 font-mono text-[11px] text-brand-300/80">{row.field_semantic_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </Card>
    </div>
  );
}

function exportDictionary(rows) {
  navigator.clipboard?.writeText(JSON.stringify(rows, null, 2)).then(() => {});
}
