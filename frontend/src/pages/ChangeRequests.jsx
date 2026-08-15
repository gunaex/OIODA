import React, { useCallback, useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useWorkspace } from "../App.jsx";
import { Button, Card, Empty, ErrorNote, Field, StatusBadge, inputClass } from "../components/ui.jsx";

export function ChangeRequests() {
  const { project } = useWorkspace();
  const [rows, setRows] = useState([]);
  const [artifacts, setArtifacts] = useState([]);
  const [change, setChange] = useState("");
  const [reason, setReason] = useState("");
  const [affected, setAffected] = useState("");
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    if (!project) return;
    api.get(`/projects/${project.id}/change-requests`).then(setRows).catch(setError);
    api.get(`/projects/${project.id}/artifacts`).then(setArtifacts).catch(() => {});
  }, [project?.id]);
  useEffect(load, [load]);

  async function create(e) {
    e.preventDefault();
    setError(null);
    const ids = affected.split(/[\s,]+/).filter(Boolean);
    try {
      await api.post("/change-requests", {
        project_id: project.id, requested_change: change, reason,
        affected_semantic_ids: ids,
      });
      setChange(""); setReason(""); setAffected("");
      load();
    } catch (err) { setError(err); }
  }

  async function implement(cr) {
    setError(null);
    try {
      await api.post(`/change-requests/${cr.id}/implement`, {
        artifact_revision_map: artifacts.length
          ? { [artifacts[0].id]: { note: `change from ${cr.code}`, from: cr.code } }
          : {},
      });
      load();
    } catch (err) { setError(err); }
  }

  return (
    <div className="space-y-4">
      <ErrorNote error={error} />
      <Card title="Change Requests — a CR spawns new revisions; it never mutates a confirmed baseline">
        {rows.length === 0 && <Empty>No change requests.</Empty>}
        <table className="w-full text-[13px]">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wider text-slate-500">
              <th className="pb-2">Code</th><th className="pb-2">Change</th><th className="pb-2">Affected</th>
              <th className="pb-2">Status</th><th className="pb-2">Release</th><th className="pb-2" />
            </tr>
          </thead>
          <tbody>
            {rows.map((cr) => (
              <tr key={cr.id} className="border-t border-line/60">
                <td className="py-2 font-mono text-brand-300">{cr.code}</td>
                <td className="max-w-72 py-2 text-slate-200">{cr.requested_change}</td>
                <td className="py-2 font-mono text-[11px] text-slate-500">{cr.affected_semantic_ids.join(", ")}</td>
                <td className="py-2"><StatusBadge status={cr.status} /></td>
                <td className="py-2 text-slate-500">{cr.target_release || "—"}</td>
                <td className="py-2">
                  {cr.status === "OPEN" && (
                    <Button onClick={() => implement(cr)}>Implement (spawn revision)</Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card title="New change request">
        <form onSubmit={create} className="space-y-3">
          <Field label="Requested change">
            <input className={inputClass} value={change} onChange={(e) => setChange(e.target.value)} placeholder="Add one more approval step" required />
          </Field>
          <div className="flex gap-3">
            <div className="flex-1">
              <Field label="Reason"><input className={inputClass} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
            </div>
            <div className="flex-1">
              <Field label="Affected semantic IDs (comma separated)">
                <input className={inputClass} value={affected} onChange={(e) => setAffected(e.target.value)} placeholder="REQ-0001" required />
              </Field>
            </div>
          </div>
          <Button variant="primary" disabled={!change || !affected}>Create CR</Button>
        </form>
      </Card>
    </div>
  );
}
