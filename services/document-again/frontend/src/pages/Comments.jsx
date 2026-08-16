import React, { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useWorkspace } from "../App.jsx";
import { Card, Empty } from "../components/ui.jsx";
import { StatusBadge } from "../components/ui.jsx";

export function Comments() {
  const { project, setFocus } = useWorkspace();
  const [rows, setRows] = useState([]);

  useEffect(() => {
    if (project) api.get(`/projects/${project.id}/annotations`).then(setRows).catch(() => {});
  }, [project?.id]);

  return (
    <Card title="Comments & annotations — every row is anchored to a semantic object, coordinates are optional placement only">
      {rows.length === 0 && <Empty>No annotations yet. Use the context panel on the right to anchor one.</Empty>}
      <table className="w-full text-[13px]">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wider text-slate-500">
            <th className="pb-2">Anchor</th><th className="pb-2">Type</th><th className="pb-2">Content</th>
            <th className="pb-2">Status</th><th className="pb-2">By</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((a) => (
            <tr key={a.id} className="cursor-pointer border-t border-line/60 hover:bg-surface-2" onClick={() => setFocus(a.anchor_semantic_id, a.anchor_semantic_id)}>
              <td className="py-1.5 font-mono text-[12px] text-brand-300">{a.anchor_semantic_id}</td>
              <td className="py-1.5 text-slate-400">{a.type}</td>
              <td className="max-w-96 py-1.5 text-slate-200">{a.content}</td>
              <td className="py-1.5"><StatusBadge status={a.status} /></td>
              <td className="py-1.5 text-slate-500">{a.created_by}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
