import React, { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useWorkspace } from "../App.jsx";
import { Card, Empty, ErrorNote, inputClass } from "../components/ui.jsx";

export function Audit() {
  const { project } = useWorkspace();
  const [rows, setRows] = useState([]);
  const [error, setError] = useState(null);
  const [actor, setActor] = useState("");
  const [action, setAction] = useState("");
  const [objectId, setObjectId] = useState("");

  useEffect(() => {
    if (!project) return;
    const params = new URLSearchParams({ project_id: project.id });
    if (actor) params.set("actor_id", actor);
    if (action) params.set("action", action);
    if (objectId) params.set("object_id", objectId);
    api.get(`/audit-events?${params}`).then(setRows).catch(setError);
  }, [project?.id, actor, action, objectId]);

  return (
    <div className="space-y-4">
      <ErrorNote error={error} />
      <Card title="Audit trail — immutable action history (not editable comments)">
        <div className="mb-3 flex flex-wrap gap-2">
          <input className={inputClass} placeholder="actor id" value={actor} onChange={(e) => setActor(e.target.value)} />
          <input className={inputClass} placeholder="action" value={action} onChange={(e) => setAction(e.target.value)} />
          <input className={inputClass} placeholder="object id" value={objectId} onChange={(e) => setObjectId(e.target.value)} />
        </div>
        {rows.length === 0 && <Empty>No audit events yet.</Empty>}
        <ul className="space-y-1">
          {rows.map((e) => (
            <li key={e.id} className="flex items-center gap-3 rounded border border-line/60 bg-surface-2 px-2 py-1 text-[12px]">
              <span className="w-32 shrink-0 font-mono text-[11px] text-slate-500">{e.created_at.slice(0, 19).replace("T", " ")}</span>
              <span className="w-48 shrink-0 font-semibold text-slate-200">{e.action}</span>
              <span className="truncate font-mono text-slate-400">{e.object_type}:{e.object_id}</span>
              <span className="shrink-0 text-slate-500">actor {e.actor_id || "—"}</span>
              {e.baseline_id && <span className="shrink-0 font-mono text-brand-300">{e.baseline_id}</span>}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
