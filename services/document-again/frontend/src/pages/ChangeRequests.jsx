import React, { useCallback, useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useWorkspace } from "../App.jsx";
import { Button, Card, Empty, ErrorNote, Field, StatusBadge, inputClass } from "../components/ui.jsx";

/*
 * Controlled-change workspace. A CR links affected semantic objects,
 * shows deterministic impact, and implements by spawning NEW revisions —
 * it never mutates an old confirmed baseline.
 */
export function ChangeRequests() {
  const { project } = useWorkspace();
  const [rows, setRows] = useState([]);
  const [artifacts, setArtifacts] = useState([]);
  const [selected, setSelected] = useState(null); // detailed CR
  const [error, setError] = useState(null);

  // create form
  const [change, setChange] = useState("");
  const [reason, setReason] = useState("");
  const [affected, setAffected] = useState("");
  const [requestedBy, setRequestedBy] = useState("");
  const [release, setRelease] = useState("");
  const [schedule, setSchedule] = useState("");
  const [commercial, setCommercial] = useState("");
  const [implTargets, setImplTargets] = useState({});

  const load = useCallback(() => {
    if (!project) return;
    api.get(`/projects/${project.id}/change-requests`).then(setRows).catch(setError);
    api.get(`/projects/${project.id}/artifacts`).then(setArtifacts).catch(() => {});
  }, [project?.id]);
  useEffect(load, [load]);

  function openDetail(cr) {
    setSelected(cr.id);
    api.get(`/change-requests/${cr.id}`).then(setSelected).catch(setError);
  }

  async function create(e) {
    e.preventDefault();
    setError(null);
    const ids = affected.split(/[\s,]+/).filter(Boolean);
    try {
      const created = await api.post("/change-requests", {
        project_id: project.id, requested_change: change, reason: reason || null,
        affected_semantic_ids: ids, requested_by: requestedBy || null,
        target_release: release || null, schedule_impact: schedule || null,
        commercial_impact: commercial || null,
      });
      setChange(""); setReason(""); setAffected(""); setRelease(""); setSchedule(""); setCommercial("");
      load();
      openDetail(created);
    } catch (err) { setError(err); }
  }

  async function implement(cr) {
    setError(null);
    const map = {};
    Object.entries(implTargets).forEach(([artifactId, checked]) => {
      if (checked) map[artifactId] = { note: cr.requested_change, from_cr: cr.code };
    });
    try {
      await api.post(`/change-requests/${cr.id}/implement`, { artifact_revision_map: map });
      setImplTargets({});
      load();
      openDetail({ id: cr.id });
    } catch (err) { setError(err); }
  }

  return (
    <div className="space-y-4">
      <ErrorNote error={error} />

      <Card title="Change Requests — spawn new revisions, never mutate a confirmed baseline">
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
              <tr key={cr.id} className="cursor-pointer border-t border-line/60 hover:bg-surface-2" onClick={() => openDetail(cr)}>
                <td className="py-2 font-mono text-brand-300">{cr.code}</td>
                <td className="max-w-72 py-2 text-slate-200">{cr.requested_change}</td>
                <td className="py-2 font-mono text-[11px] text-slate-500">{cr.affected_semantic_ids.join(", ")}</td>
                <td className="py-2"><StatusBadge status={cr.status} /></td>
                <td className="py-2 text-slate-500">{cr.target_release || "—"}</td>
                <td className="py-2 text-right">
                  <Button onClick={(e) => { e.stopPropagation(); openDetail(cr); }}>Open</Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <div className="grid grid-cols-2 gap-4">
        <Card title="New change request">
          <form onSubmit={create} className="space-y-3">
            <Field label="Requested change">
              <input className={inputClass} value={change} onChange={(e) => setChange(e.target.value)} placeholder="Add one more approval step" required />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Requested by"><input className={inputClass} value={requestedBy} onChange={(e) => setRequestedBy(e.target.value)} /></Field>
              <Field label="Target release"><input className={inputClass} value={release} onChange={(e) => setRelease(e.target.value)} /></Field>
              <Field label="Reason"><input className={inputClass} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
              <Field label="Schedule impact"><input className={inputClass} value={schedule} onChange={(e) => setSchedule(e.target.value)} /></Field>
            </div>
            <Field label="Affected semantic IDs (comma separated)">
              <input className={inputClass} value={affected} onChange={(e) => setAffected(e.target.value)} placeholder="REQ-0001, tbl_orders" required />
            </Field>
            <Field label="Commercial impact"><input className={inputClass} value={commercial} onChange={(e) => setCommercial(e.target.value)} /></Field>
            <Button variant="primary" disabled={!change || !affected}>Create CR</Button>
          </form>
        </Card>

        {selected && typeof selected !== "string" && (
          <Card title={`${selected.code} — detail`}>
            <div className="space-y-3 text-[13px]">
              <p className="text-slate-300">{selected.requested_change}</p>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[12px] text-slate-400">
                <span>Requested by: <b className="text-slate-200">{selected.requested_by || "—"}</b></span>
                <span>Status: <StatusBadge status={selected.status} /></span>
                <span>Reason: {selected.reason || "—"}</span>
                <span>Release: {selected.target_release || "—"}</span>
                <span>Schedule: {selected.schedule_impact || "—"}</span>
                <span>Commercial: {selected.commercial_impact || "—"}</span>
              </div>

              <div>
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Affected objects + impact</p>
                {selected.affected.map((a) => (
                  <div key={a.semantic_id} className="rounded border border-line bg-surface-2 px-2 py-1 text-[12px]">
                    <span className="font-mono text-brand-300">{a.semantic_id}</span>
                    <span className="ml-2 text-slate-500">({a.object_type})</span>
                    {selected.impact[a.semantic_id] && (
                      <span className="ml-2 text-slate-400">
                        ↓ {selected.impact[a.semantic_id].downstream.length} · ↑ {selected.impact[a.semantic_id].upstream.length}
                      </span>
                    )}
                  </div>
                ))}
              </div>

              <div>
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Spawned revisions (before → after)</p>
                {selected.spawned_revisions.length === 0 && <p className="text-[12px] text-slate-600">not implemented yet</p>}
                {selected.spawned_revisions.map((r) => (
                  <div key={r.revision_id} className="flex items-center gap-2 text-[12px] text-slate-300">
                    <span>{r.artifact_title}</span>
                    <span className="text-slate-500">before: {r.based_on_revision_id ? "…" + r.based_on_revision_id.slice(-6) : "—"} →</span>
                    <span className="font-mono text-brand-300">after: r{r.revision_number}</span>
                    <StatusBadge status={r.status} />
                  </div>
                ))}
              </div>

              {selected.status === "OPEN" && (
                <div className="border-t border-line pt-3">
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Implement — spawn new revisions for:</p>
                  <div className="mb-2 space-y-1">
                    {artifacts.map((a) => (
                      <label key={a.id} className="flex items-center gap-2 text-[12px] text-slate-300">
                        <input type="checkbox" checked={!!implTargets[a.id]} onChange={(e) => setImplTargets((m) => ({ ...m, [a.id]: e.target.checked }))} />
                        {a.type} — {a.title}
                      </label>
                    ))}
                  </div>
                  <Button variant="primary" onClick={() => implement(selected)} disabled={!Object.values(implTargets).some(Boolean)}>Implement</Button>
                </div>
              )}
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
