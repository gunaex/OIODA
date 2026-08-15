import React, { useCallback, useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { api } from "../api/client.js";
import { useWorkspace } from "../App.jsx";
import { Button, Card, Empty, ErrorNote, Field, inputClass } from "../components/ui.jsx";

/*
 * Database design workspace. Canonical Model → Diagram View → Document
 * View → Data Dictionary. The structured model is the truth; this page
 * only renders it. The ERD canvas itself is P1.
 */
export function Database() {
  return (
    <Routes>
      <Route index element={<ModelPage />} />
      <Route path="dictionary" element={<DictionaryPage />} />
    </Routes>
  );
}

function Tabs() {
  return (
    <div className="mb-4 flex gap-1 border-b border-line pb-2 text-[13px]">
      <NavLink
        to="."
        end
        className={({ isActive }) => (isActive ? "text-brand-300" : "text-slate-500 hover:text-slate-300") + " px-2 py-1"}
      >
        Schemas / Tables / Fields
      </NavLink>
      <NavLink
        to="dictionary"
        className={({ isActive }) => (isActive ? "text-brand-300" : "text-slate-500 hover:text-slate-300") + " px-2 py-1"}
      >
        Data Dictionary
      </NavLink>
    </div>
  );
}

function ModelPage() {
  const { project, setFocus } = useWorkspace();
  const [schemas, setSchemas] = useState([]);
  const [error, setError] = useState(null);
  const [schemaName, setSchemaName] = useState("");
  const [tableName, setTableName] = useState("");
  const [fieldName, setFieldName] = useState("");
  const [fieldType, setFieldType] = useState("VARCHAR");
  const [fieldFk, setFieldFk] = useState(false);
  const [fieldRef, setFieldRef] = useState("");
  const [activeTable, setActiveTable] = useState(null);

  const load = useCallback(() => {
    if (project) api.get(`/projects/${project.id}/db-schemas`).then(setSchemas).catch(setError);
  }, [project?.id]);
  useEffect(load, [load]);

  const schema = schemas[0]; // P0: single working schema per project view

  async function createSchema(e) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/db-schemas", {
        project_id: project.id, name: schemaName,
        semantic_id: `sch_${schemaName.toLowerCase()}`,
      });
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
      setActiveTable(created.id);
      load();
    } catch (err) { setError(err); }
  }

  async function createField(e) {
    e.preventDefault();
    setError(null);
    const table = schema.tables.find((t) => t.id === activeTable);
    if (!table) return;
    try {
      await api.post("/db-fields", {
        table_id: table.id, name: fieldName, data_type: fieldType,
        foreign_key: fieldFk, reference: fieldRef || null,
      });
      setFieldName(""); setFieldRef(""); setFieldFk(false);
      load();
    } catch (err) { setError(err); }
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
        <div className="grid grid-cols-[repeat(auto-fill,minmax(320px,1fr))] gap-4">
          {schema.tables.map((t) => (
            <Card
              key={t.id}
              title={t.name}
              actions={<span className="font-mono text-[11px] text-slate-500">{t.semantic_id}</span>}
              className={activeTable === t.id ? "ring-1 ring-brand-600" : ""}
            >
              <button className="mb-2 text-[11px] text-brand-400 hover:underline" onClick={() => { setActiveTable(t.id); setFocus(t.semantic_id, t.semantic_id); }}>
                focus context panel here
              </button>
              <table className="w-full text-[12px]">
                <tbody>
                  {t.fields.length === 0 && <tr><td className="text-slate-500">No fields yet.</td></tr>}
                  {t.fields.map((f) => (
                    <tr key={f.id} className="border-t border-line/50">
                      <td className="py-1">
                        <button className="font-mono text-slate-300 hover:text-brand-300" onClick={() => setFocus(f.semantic_id, f.semantic_id)} title={f.semantic_id}>
                          {f.name}{f.primary_key ? " 🔑" : ""}{f.foreign_key ? " 🔗" : ""}
                        </button>
                      </td>
                      <td className="py-1 text-slate-500">{f.data_type}{f.length ? `(${f.length})` : ""}</td>
                      <td className="py-1 text-right text-slate-600">{f.reference || ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          ))}
        </div>
      )}
      {schema && (
        <div className="grid grid-cols-2 gap-4">
          <Card title="Add table">
            <form onSubmit={createTable} className="flex items-end gap-3">
              <Field label="Table name"><input className={inputClass} value={tableName} onChange={(e) => setTableName(e.target.value)} required /></Field>
              <Button variant="primary" disabled={!tableName}>Create table</Button>
            </form>
          </Card>
          <Card title={activeTable ? `Add field — ${schema.tables.find((t) => t.id === activeTable)?.name}` : "Add field (select a table first)"}>
            <form onSubmit={createField} className="flex flex-wrap items-end gap-3">
              <Field label="Name"><input className={inputClass} value={fieldName} onChange={(e) => setFieldName(e.target.value)} required disabled={!activeTable} /></Field>
              <Field label="Type">
                <select className={inputClass} value={fieldType} onChange={(e) => setFieldType(e.target.value)}>
                  {["VARCHAR", "UUID", "INT", "BIGINT", "DECIMAL", "BOOLEAN", "TIMESTAMP", "TEXT", "JSON"].map((t) => <option key={t}>{t}</option>)}
                </select>
              </Field>
              <label className="flex items-center gap-1.5 pb-1.5 text-[12px] text-slate-400">
                <input type="checkbox" checked={fieldFk} onChange={(e) => setFieldFk(e.target.checked)} /> FK
              </label>
              {fieldFk && <Field label="Reference"><input className={inputClass} value={fieldRef} onChange={(e) => setFieldRef(e.target.value)} placeholder="users.id" /></Field>}
              <Button variant="primary" disabled={!activeTable || !fieldName}>Add field</Button>
            </form>
          </Card>
        </div>
      )}
    </div>
  );
}

function DictionaryPage() {
  const { project } = useWorkspace();
  const [schemas, setSchemas] = useState([]);
  const [dictionary, setDictionary] = useState([]);
  const schema = schemas[0];

  useEffect(() => {
    if (project) api.get(`/projects/${project.id}/db-schemas`).then(setSchemas).catch(() => {});
  }, [project?.id]);
  useEffect(() => {
    if (schema) api.get(`/db-schemas/${schema.id}/data-dictionary`).then(setDictionary).catch(() => {});
  }, [schema?.id]);

  return (
    <div className="space-y-4">
      <Tabs />
      <Card title="Data Dictionary — generated view over the canonical model (never edited directly)">
        {!schema && <Empty>No schema yet.</Empty>}
        {schema && dictionary.length === 0 && <Empty>No fields yet.</Empty>}
        {dictionary.length > 0 && (
          <table className="w-full text-[12px]">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wider text-slate-500">
                <th className="pb-2">Table</th><th className="pb-2">Field</th><th className="pb-2">Type</th>
                <th className="pb-2">Null</th><th className="pb-2">Key</th><th className="pb-2">Reference</th><th className="pb-2">Semantic ID</th>
              </tr>
            </thead>
            <tbody>
              {dictionary.map((row) => (
                <tr key={row.field_semantic_id} className="border-t border-line/50">
                  <td className="py-1 text-slate-300">{row.table}</td>
                  <td className="py-1 font-mono text-slate-200">{row.field}</td>
                  <td className="py-1 text-slate-500">{row.data_type}{row.length ? `(${row.length})` : ""}</td>
                  <td className="py-1 text-slate-500">{row.nullable ? "Y" : "N"}</td>
                  <td className="py-1 text-slate-500">{row.primary_key ? "PK" : row.foreign_key ? "FK" : ""}</td>
                  <td className="py-1 text-slate-500">{row.reference || ""}</td>
                  <td className="py-1 font-mono text-[11px] text-brand-300/80">{row.field_semantic_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
