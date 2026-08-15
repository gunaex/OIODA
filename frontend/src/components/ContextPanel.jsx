import React, { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useWorkspace } from "../App.jsx";
import { Button, StatusBadge, inputClass } from "./ui.jsx";

/*
 * Right context panel: comments (annotations), trace links, impact —
 * all bound to the focused semantic object, never to layout positions.
 */
const TABS = ["Comments", "Trace", "Impact"];

const ANNOTATION_TYPES = [
  "COMMENT", "QUESTION", "CLARIFICATION", "DECISION", "ASSUMPTION", "ISSUE", "CHANGE_REQUEST",
];

const FILTERS = ["All", "Open", "Resolved"];

export function ContextPanel() {
  const { project, focus } = useWorkspace();
  const [tab, setTab] = useState("Comments");
  const [annotations, setAnnotations] = useState([]);
  const [traces, setTraces] = useState([]);
  const [impact, setImpact] = useState(null);
  const [draft, setDraft] = useState("");
  const [type, setType] = useState("COMMENT");
  const [filter, setFilter] = useState("All");
  const [error, setError] = useState(null);

  useEffect(() => {
    setAnnotations([]);
    setTraces([]);
    setImpact(null);
    if (!project || !focus) return;
    api.get(`/projects/${project.id}/annotations`)
      .then((rows) => setAnnotations(rows.filter((a) => a.anchor_semantic_id === focus.semanticId)))
      .catch(() => {});
    api.get(`/projects/${project.id}/traces`)
      .then((rows) => setTraces(rows.filter((t) => t.source === focus.semanticId || t.target === focus.semanticId)))
      .catch(() => {});
    api.get(`/projects/${project.id}/impact/${encodeURIComponent(focus.semanticId)}`)
      .then(setImpact)
      .catch(() => {});
  }, [project?.id, focus?.semanticId]);

  async function addComment() {
    if (!draft.trim() || !focus) return;
    setError(null);
    try {
      const created = await api.post("/annotations", {
        project_id: project.id,
        anchor_object_type: "SEMANTIC_OBJECT",
        anchor_semantic_id: focus.semanticId,
        content: draft.trim(),
        type,
      });
      setAnnotations((a) => [...a, created]);
      setDraft("");
    } catch (e) {
      setError(e);
    }
  }

  async function setStatus(annotation, status) {
    setError(null);
    try {
      const updated = await api.post(`/annotations/${annotation.id}/status/${status}`);
      setAnnotations((a) => a.map((x) => (x.id === annotation.id ? updated : x)));
    } catch (e) {
      setError(e);
    }
  }

  const visible = annotations.filter((a) =>
    filter === "All" ? true : filter === "Open" ? a.status !== "RESOLVED" : a.status === "RESOLVED"
  );
  const openCount = annotations.filter((a) => a.status !== "RESOLVED").length;

  return (
    <aside className="flex w-80 shrink-0 flex-col border-l border-line bg-surface-1">
      <div className="flex border-b border-line">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 px-3 py-2 text-[12px] font-medium ${
              tab === t ? "border-b-2 border-brand-500 text-slate-200" : "text-slate-500 hover:text-slate-300"
            }`}
          >
            {t}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-3 text-[13px]">
        {!focus && <p className="text-slate-500">Select an object (requirement, section, table, field, artifact…) to anchor this panel.</p>}

        {focus && tab === "Comments" && (
          <div className="space-y-3">
            <div className="flex items-center justify-between text-[11px] text-slate-500">
              <span>{annotations.length} total · {openCount} open</span>
              <span className="font-mono text-slate-600">{focus.semanticId}</span>
            </div>

            <div className="flex gap-1">
              {FILTERS.map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`rounded px-2 py-0.5 text-[11px] ${
                    filter === f ? "bg-brand-600/20 text-brand-100" : "text-slate-500 hover:bg-surface-2"
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>

            {visible.length === 0 && <p className="text-slate-500">No annotations on {focus.label}.</p>}

            {visible.map((a) => (
              <div key={a.id} className="rounded border border-line bg-surface-2 p-2">
                <div className="flex items-center justify-between text-[11px] text-slate-500">
                  <span>{a.created_by} · {a.type}</span>
                  <StatusBadge status={a.status} />
                </div>
                <p className="mt-1 text-slate-300">{a.content}</p>
                <div className="mt-2 flex gap-2">
                  {a.status !== "RESOLVED" ? (
                    <button className="text-[11px] text-brand-300 hover:text-brand-100" onClick={() => setStatus(a, "RESOLVED")}>resolve</button>
                  ) : (
                    <button className="text-[11px] text-amber-300 hover:text-amber-100" onClick={() => setStatus(a, "REOPENED")}>reopen</button>
                  )}
                </div>
              </div>
            ))}

            <div className="space-y-2 border-t border-line pt-3">
              <select className={inputClass} value={type} onChange={(e) => setType(e.target.value)}>
                {ANNOTATION_TYPES.map((t) => <option key={t} value={t}>{t.replaceAll("_", " ")}</option>)}
              </select>
              <textarea
                className={`${inputClass} min-h-16 w-full`}
                placeholder="Annotate this semantic object…"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
              />
              {error && <p className="text-[12px] text-red-400">{error.message}</p>}
              <Button variant="primary" onClick={addComment}>Comment</Button>
            </div>
          </div>
        )}

        {focus && tab === "Trace" && (
          <div className="space-y-2">
            {traces.length === 0 && <p className="text-slate-500">No trace links involving {focus.label}.</p>}
            {traces.map((t) => (
              <div key={t.id} className="rounded border border-line bg-surface-2 p-2">
                <p className="text-slate-300">{t.source} <span className="text-brand-400">—{t.relation}→</span> {t.target}</p>
                {t.revision_context && <p className="text-[11px] text-slate-500">rev: {t.revision_context}</p>}
              </div>
            ))}
          </div>
        )}

        {focus && tab === "Impact" && (
          <div className="space-y-3">
            {!impact && <p className="text-slate-500">No impact data.</p>}
            {impact && (
              <>
                <div>
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Downstream (affected by this)</p>
                  {impact.downstream.length === 0 && <p className="text-slate-500">none</p>}
                  {impact.downstream.map((d, i) => (
                    <p key={i} className="text-slate-300">{d.semantic_id} <span className="text-slate-500">({d.relation})</span></p>
                  ))}
                </div>
                <div>
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Upstream (this depends on)</p>
                  {impact.upstream.length === 0 && <p className="text-slate-500">none</p>}
                  {impact.upstream.map((u, i) => (
                    <p key={i} className="text-slate-300">{u.semantic_id} <span className="text-slate-500">({u.relation})</span></p>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
