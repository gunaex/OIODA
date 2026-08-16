import React, { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useWorkspace } from "../App.jsx";
import { Button, Card, Empty, ErrorNote, Field, inputClass } from "../components/ui.jsx";

export function Baselines() {
  const { project } = useWorkspace();
  const [rows, setRows] = useState([]);
  const [artifacts, setArtifacts] = useState([]);
  const [name, setName] = useState("");
  const [error, setError] = useState(null);

  function load() {
    if (!project) return;
    api.get(`/projects/${project.id}/baselines`).then(setRows).catch(setError);
    api.get(`/projects/${project.id}/artifacts`)
      .then((arts) => setArtifacts(arts))
      .catch(() => {});
  }
  useEffect(load, [project?.id]);

  async function freeze(e) {
    e.preventDefault();
    setError(null);
    // Freeze the current confirmed revision of every artifact that has one.
    const pairs = await Promise.all(
      artifacts.map(async (a) => {
        const full = await api.get(`/artifacts/${a.id}`);
        const confirmed = full.revisions.find((r) => r.status === "CONFIRMED");
        return confirmed ? confirmed.id : null;
      })
    );
    const ids = pairs.filter(Boolean);
    if (ids.length === 0) {
      setError(new Error("No confirmed revisions to freeze. Confirm at least one UR/DR revision first."));
      return;
    }
    try {
      await api.post("/baselines", {
        project_id: project.id, name, artifact_revision_ids: ids,
        description: "Frozen from workspace",
      });
      setName("");
      load();
    } catch (err) { setError(err); }
  }

  return (
    <div className="space-y-4">
      <ErrorNote error={error} />
      <Card title="Baselines — frozen artifact→revision bindings; later revisions never alter these">
        {rows.length === 0 && <Empty>No baselines yet. Confirm revisions, then freeze.</Empty>}
        {rows.map((b) => (
          <div key={b.id} className="mb-3 rounded border border-line bg-surface-2 p-3">
            <p className="text-[13px] font-medium text-slate-200">
              {b.name} <span className="ml-2 text-[11px] text-slate-500">{b.created_at.slice(0, 19).replace("T", " ")} by {b.created_by}</span>
            </p>
            <ul className="mt-2 space-y-1">
              {b.bindings.map((bind) => (
                <li key={bind.artifact_id} className="flex gap-2 text-[12px]">
                  <span className="text-slate-400">{bind.semantic_object_type || "ARTIFACT"}</span>
                  <span className="font-mono text-brand-300">{bind.artifact_id}</span>
                  <span className="text-slate-600">→</span>
                  <span className="font-mono text-slate-300">{bind.artifact_revision_id}</span>
                </li>
              ))}
            </ul>
            <a href={`/api/baselines/${b.id}/package`} className="mt-2 inline-block text-[11px] text-brand-300 hover:text-brand-100">⬇ download design package (ZIP)</a>
          </div>
        ))}
      </Card>

      <Card title="Freeze baseline (binds every artifact's current CONFIRMED revision)">
        <form onSubmit={freeze} className="flex items-end gap-3">
          <Field label="Baseline name">
            <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} placeholder="Order Approval 1.0" required />
          </Field>
          <Button variant="primary">Freeze</Button>
        </form>
      </Card>
    </div>
  );
}
