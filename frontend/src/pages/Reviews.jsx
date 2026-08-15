import React, { useCallback, useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useWorkspace } from "../App.jsx";
import { Button, Card, Empty, ErrorNote, Field, Modal, StatusBadge, inputClass } from "../components/ui.jsx";

/*
 * Review inbox + activity timeline. Reviews happen on artifact revisions:
 * submit → comment/question/clarification → resolve → confirm.
 */
export function Reviews() {
  const { project, setFocus } = useWorkspace();
  const [items, setItems] = useState([]);
  const [timeline, setTimeline] = useState([]);
  const [error, setError] = useState(null);
  const [confirming, setConfirming] = useState(null); // revision object
  const [comment, setComment] = useState("");
  const [evidence, setEvidence] = useState("");

  const load = useCallback(() => {
    if (!project) return;
    api.get(`/projects/${project.id}/artifacts`).then(async (artifacts) => {
      const rows = [];
      for (const a of artifacts) {
        const full = await api.get(`/artifacts/${a.id}`);
        for (const r of full.revisions) {
          if (r.status === "IN_REVIEW") {
            const anns = await api.get(`/revisions/${r.id}/annotations`).catch(() => []);
            rows.push({
              ...r,
              artifact_title: a.title,
              artifact_type: a.type,
              open_annotations: anns.filter((x) => x.status !== "RESOLVED").length,
              total_annotations: anns.length,
            });
          }
        }
      }
      setItems(rows);
    }).catch(setError);

    api.get(`/projects/${project.id}/timeline`).then(setTimeline).catch(() => {});
  }, [project?.id]);

  useEffect(load, [load]);

  async function confirm() {
    setError(null);
    let ev = null;
    if (evidence.trim()) {
      try {
        ev = JSON.parse(evidence);
      } catch {
        setError(new Error("Evidence must be valid JSON (or empty)"));
        return;
      }
    }
    try {
      await api.post(`/revisions/${confirming.id}/confirm`, { comment: comment || null, evidence: ev });
      setConfirming(null);
      setComment("");
      setEvidence("");
      load();
    } catch (err) {
      setError(err);
    }
  }

  return (
    <div className="space-y-4">
      <ErrorNote error={error} />

      <Card title="Review inbox — revisions awaiting confirmation">
        {items.length === 0 && <Empty>Nothing in review. Open a UR/DR draft and submit it for review.</Empty>}
        {items.map((r) => (
          <div key={r.id} className="mb-2 flex items-center justify-between rounded border border-line bg-surface-2 px-3 py-2">
            <div className="flex items-center gap-3">
              <span className="rounded bg-brand-600/20 px-1.5 py-0.5 text-[11px] font-semibold text-brand-200">{r.artifact_type}</span>
              <div>
                <p className="text-[13px] text-slate-200">{r.artifact_title} · r{r.revision_number}</p>
                <p className="text-[11px] text-slate-500">
                  {r.total_annotations} annotations · {r.open_annotations} open
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status={r.status} />
              <Button variant="primary" onClick={() => setConfirming(r)}>Confirm</Button>
            </div>
          </div>
        ))}
      </Card>

      <Card title="Activity timeline">
        {timeline.length === 0 && <Empty>No activity yet.</Empty>}
        <ul className="space-y-1">
          {timeline.slice().reverse().map((e, i) => (
            <li key={i} className="flex items-start gap-3 border-b border-line/50 py-1.5 text-[12px]">
              <span className="w-40 shrink-0 text-slate-500">{(e.at || "").slice(0, 19).replace("T", " ")}</span>
              <span className="w-40 shrink-0 font-mono text-[11px] text-brand-300">{e.kind}</span>
              <span className="min-w-0 flex-1 text-slate-300">{e.label}</span>
              <span className="shrink-0 text-slate-500">{e.actor}</span>
            </li>
          ))}
        </ul>
      </Card>

      <Modal
        title="Confirm revision"
        open={!!confirming}
        onClose={() => setConfirming(null)}
        footer={
          <>
            <Button onClick={() => setConfirming(null)}>Cancel</Button>
            <Button variant="primary" onClick={confirm}>Confirm (immutable)</Button>
          </>
        }
      >
        {confirming && (
          <div className="space-y-3">
            <p className="text-[13px] text-slate-300">
              <span className="font-semibold">{confirming.artifact_title}</span> · r{confirming.revision_number}
              {" "}— confirming makes this revision immutable. To change it later you must clone a new revision.
            </p>
            <Field label="Confirmation comment">
              <textarea className={`${inputClass} min-h-16 w-full`} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="e.g. UR reviewed and approved" />
            </Field>
            <Field label="Evidence (JSON, optional)">
              <textarea className={`${inputClass} min-h-16 w-full font-mono text-[12px]`} value={evidence} onChange={(e) => setEvidence(e.target.value)} placeholder='{"review": "walkthrough"}' />
            </Field>
          </div>
        )}
      </Modal>
    </div>
  );
}