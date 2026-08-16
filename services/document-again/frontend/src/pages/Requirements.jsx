import React, { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useWorkspace } from "../App.jsx";
import { Button, Card, Empty, Field, StatusBadge, inputClass } from "../components/ui.jsx";

export function Requirements() {
  const { project, setFocus } = useWorkspace();
  const [rows, setRows] = useState([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState(null);

  useEffect(() => {
    if (project) api.get(`/projects/${project.id}/requirements`).then(setRows).catch(setError);
  }, [project?.id]);

  async function create(e) {
    e.preventDefault();
    setError(null);
    try {
      const created = await api.post("/requirements", {
        project_id: project.id, title, description, priority: "MUST",
      });
      setRows((r) => [...r, created]);
      setTitle("");
      setDescription("");
    } catch (err) {
      setError(err);
    }
  }

  return (
    <div className="space-y-4">
      <Card title="Requirement Register — canonical requirements live here, not inside document text">
        {rows.length === 0 && <Empty>No requirements yet.</Empty>}
        <table className="w-full text-[13px]">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wider text-slate-500">
              <th className="pb-2">Code</th><th className="pb-2">Title</th><th className="pb-2">Priority</th><th className="pb-2">Status</th><th className="pb-2">Source</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={r.id}
                className="cursor-pointer border-t border-line/60 hover:bg-surface-2"
                onClick={() => setFocus(r.code, r.code)}
              >
                <td className="py-1.5 font-mono text-brand-300">{r.code}</td>
                <td className="py-1.5 text-slate-200">{r.title}</td>
                <td className="py-1.5 text-slate-400">{r.priority}</td>
                <td className="py-1.5"><StatusBadge status={r.status} /></td>
                <td className="py-1.5 text-slate-500">{r.source_type || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card title="Add requirement">
        <form onSubmit={create} className="flex flex-wrap items-end gap-3">
          <div className="min-w-64 flex-1">
            <Field label="Title">
              <input className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} required />
            </Field>
          </div>
          <div className="min-w-64 flex-1">
            <Field label="Description">
              <input className={inputClass} value={description} onChange={(e) => setDescription(e.target.value)} />
            </Field>
          </div>
          <Button variant="primary" disabled={!title}>Create</Button>
        </form>
        {error && <p className="mt-2 text-[12px] text-red-400">{error.message}</p>}
      </Card>
    </div>
  );
}
