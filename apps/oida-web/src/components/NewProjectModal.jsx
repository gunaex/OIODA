import { useState } from "react";
import { documentApi } from "../api";

export default function NewProjectModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    name: "",
    key: "",
    description: "",
    customer: "",
    owner: "Owner",
    project_type: "estimate",
    source: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  function set(k, v) {
    setForm((f) => {
      const next = { ...f, [k]: v };
      if (k === "name" && !f.key) {
        next.key = v.toUpperCase().replace(/[^A-Z0-9]+/g, "").slice(0, 8);
      }
      return next;
    });
  }

  async function save() {
    if (!form.name.trim()) { setError("Project name is required."); return; }
    if (!form.key.trim()) { setError("Project key/code is required."); return; }
    setBusy(true); setError(null);
    try {
      const created = await documentApi.createProject({
        key: form.key.trim(),
        name: form.name.trim(),
        description: form.description || null,
        metadata: {
          customer: form.customer || null,
          owner: form.owner,
          project_type: form.project_type,
          source: form.source || null,
        },
      });
      onCreated?.(created);
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-black/30 p-6" onClick={onClose}>
      <div className="mt-10 w-full max-w-xl rounded-xl border border-gray-200 bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold">New Project</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700">✕</button>
        </div>
        <p className="mt-1 text-xs text-gray-500">Creates the Document Again project authority. PM/QA/Infra state is created later, when a source exists.</p>

        <div className="mt-4 grid gap-3">
          <Field label="Project name *">
            <input className="input" value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="e.g. True Cloud Migration" />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Project code / key *">
              <input className="input" value={form.key} onChange={(e) => set("key", e.target.value)} placeholder="TCM" />
            </Field>
            <Field label="Customer / organization">
              <input className="input" value={form.customer} onChange={(e) => set("customer", e.target.value)} placeholder="Customer name" />
            </Field>
          </div>
          <Field label="Description">
            <textarea className="input min-h-16" value={form.description} onChange={(e) => set("description", e.target.value)} placeholder="What is this project about?" />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Owner">
              <input className="input" value={form.owner} onChange={(e) => set("owner", e.target.value)} />
            </Field>
            <Field label="Project type">
              <select className="input" value={form.project_type} onChange={(e) => set("project_type", e.target.value)}>
                <option value="estimate">Estimate</option>
                <option value="simple">Simple</option>
              </select>
            </Field>
          </div>
          <Field label="Source / initial requirement input (optional)">
            <textarea className="input min-h-16" value={form.source} onChange={(e) => set("source", e.target.value)} placeholder="Paste a customer requirement or SOW excerpt" />
          </Field>
        </div>

        {error && <div className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-600">{error}</div>}

        <div className="mt-4 flex items-center justify-end gap-2 border-t border-gray-100 pt-3">
          <button onClick={onClose} className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50">Cancel</button>
          <button onClick={save} disabled={busy} className="rounded-lg bg-gray-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50">
            {busy ? "Creating…" : "Create Project"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-xs font-medium text-gray-600">{label}</span>
      {children}
    </label>
  );
}
