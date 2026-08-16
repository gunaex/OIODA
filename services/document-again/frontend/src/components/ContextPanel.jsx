import React, { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useWorkspace } from "../App.jsx";
import { Button, StatusBadge, inputClass } from "./ui.jsx";
import { GLOSSARY } from "../tokens/glossary.js";

/*
 * Right context panel — the project's memory layer, bound to the focused
 * semantic object (never to layout positions).
 *
 *   Comments  — annotations (comment/question/…) with resolve/reopen
 *   Trace     — incoming / outgoing links
 *   Impact    — what this affects / depends on
 *   History   — activity timeline for this object
 *   Evidence  — decisions/assumptions/clarifications + confirmations
 *   Help      — guidance
 */
const TABS = ["Comments", "Trace", "Impact", "History", "Evidence", "Help"];

const ANNOTATION_TYPES = [
  "COMMENT", "QUESTION", "CLARIFICATION", "DECISION", "ASSUMPTION", "ISSUE", "CHANGE_REQUEST",
];
const EVIDENCE_TYPES = ["DECISION", "ASSUMPTION", "CLARIFICATION"];
const FILTERS = ["All", "Open", "Resolved"];

export function ContextPanel() {
  const { project, focus } = useWorkspace();
  const [tab, setTab] = useState("Comments");
  const [annotations, setAnnotations] = useState([]);
  const [traces, setTraces] = useState([]);
  const [impact, setImpact] = useState(null);
  const [context, setContext] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [draft, setDraft] = useState("");
  const [type, setType] = useState("COMMENT");
  const [filter, setFilter] = useState("All");
  const [error, setError] = useState(null);

  useEffect(() => {
    setAnnotations([]); setTraces([]); setImpact(null); setContext(null); setTimeline([]);
    if (!project || !focus) return;
    api.get(`/projects/${project.id}/annotations`)
      .then((rows) => setAnnotations(rows.filter((a) => a.anchor_semantic_id === focus.semanticId)))
      .catch(() => {});
    api.get(`/projects/${project.id}/traces`)
      .then((rows) => setTraces(rows.filter((t) => t.source === focus.semanticId || t.target === focus.semanticId)))
      .catch(() => {});
    api.get(`/projects/${project.id}/impact/${encodeURIComponent(focus.semanticId)}`)
      .then(setImpact).catch(() => {});
    api.get(`/projects/${project.id}/semantic-context/${encodeURIComponent(focus.semanticId)}`)
      .then(setContext).catch(() => {});
    api.get(`/projects/${project.id}/timeline?semantic_id=${encodeURIComponent(focus.semanticId)}`)
      .then(setTimeline).catch(() => {});
  }, [project?.id, focus?.semanticId]);

  async function addComment() {
    if (!draft.trim() || !focus) return;
    setError(null);
    try {
      const created = await api.post("/annotations", {
        project_id: project.id,
        anchor_object_type: context?.object_type || "SEMANTIC_OBJECT",
        anchor_semantic_id: focus.semanticId,
        content: draft.trim(),
        type,
      });
      setAnnotations((a) => [...a, created]);
      setDraft("");
    } catch (e) { setError(e); }
  }

  async function setStatus(annotation, status) {
    setError(null);
    try {
      const updated = await api.post(`/annotations/${annotation.id}/status/${status}`);
      setAnnotations((a) => a.map((x) => (x.id === annotation.id ? updated : x)));
    } catch (e) { setError(e); }
  }

  async function promote(annotation) {
    const kind = window.prompt("Promote to: decision | assumption | clarification | change_request", "decision");
    if (!kind) return;
    setError(null);
    try {
      const result = await api.post("/promote-annotation", { annotation_id: annotation.id, to_kind: kind.trim().toLowerCase() });
      setAnnotations((a) => a.map((x) => (x.id === annotation.id ? { ...x, status: "RESOLVED" } : x)));
      // eslint-disable-next-line no-alert
      window.alert(`Promoted → ${result.kind} ${result.code}`);
    } catch (e) { setError(e); }
  }

  const visible = annotations.filter((a) =>
    filter === "All" ? true : filter === "Open" ? a.status !== "RESOLVED" : a.status === "RESOLVED"
  );
  const openCount = annotations.filter((a) => a.status !== "RESOLVED").length;
  const evidenceAnnotations = annotations.filter((a) => EVIDENCE_TYPES.includes(a.type));

  return (
    <aside className="hidden w-80 shrink-0 flex-col border-l border-line bg-surface-1 2xl:flex">
      <div className="flex overflow-x-auto border-b border-line">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`shrink-0 px-2.5 py-2 text-[11px] font-medium ${
              tab === t ? "border-b-2 border-brand-500 text-slate-200" : "text-slate-500 hover:text-slate-300"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3 text-[13px]">
        {!focus && <p className="text-slate-500">Select an object (requirement, section, table, field, artifact…) to anchor this panel.</p>}

        {focus && (
          <>
            {/* object identity header */}
            <div className="mb-3 rounded border border-line bg-surface-2 p-2">
              <p className="font-mono text-[12px] text-brand-300">{focus.semanticId}</p>
              <p className="text-[11px] text-slate-400">{context?.object_type || "semantic object"}{context?.display_name ? ` — ${context.display_name}` : ""}</p>
              {context?.status && (
                <div className="mt-1 flex items-center gap-2">
                  <StatusBadge status={context.status} />
                  {context.confirmed === true && <span className="text-[11px] text-emerald-400">confirmed</span>}
                  {context.confirmed === false && <span className="text-[11px] text-amber-400">not confirmed</span>}
                </div>
              )}
            </div>

            {tab === "Comments" && (
              <div className="space-y-3">
                <div className="flex items-center justify-between text-[11px] text-slate-500">
                  <span>{annotations.length} total · {openCount} open</span>
                </div>
                <div className="flex gap-1">
                  {FILTERS.map((f) => (
                    <button key={f} onClick={() => setFilter(f)} className={`rounded px-2 py-0.5 text-[11px] ${filter === f ? "bg-brand-600/20 text-brand-100" : "text-slate-500 hover:bg-surface-2"}`}>{f}</button>
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
                      {a.status !== "RESOLVED"
                        ? <button className="text-[11px] text-brand-300 hover:text-brand-100" onClick={() => setStatus(a, "RESOLVED")}>resolve</button>
                        : <button className="text-[11px] text-amber-300 hover:text-amber-100" onClick={() => setStatus(a, "REOPENED")}>reopen</button>}
                      <button className="text-[11px] text-slate-500 hover:text-brand-300" onClick={() => promote(a)}>↗ promote</button>
                    </div>
                  </div>
                ))}
                <div className="space-y-2 border-t border-line pt-3">
                  <select className={inputClass} value={type} onChange={(e) => setType(e.target.value)}>
                    {ANNOTATION_TYPES.map((t) => <option key={t} value={t}>{t.replaceAll("_", " ")}</option>)}
                  </select>
                  <textarea className={`${inputClass} min-h-16 w-full`} placeholder="Annotate this semantic object…" value={draft} onChange={(e) => setDraft(e.target.value)} />
                  {error && <p className="text-[12px] text-red-400">{error.message}</p>}
                  <Button variant="primary" onClick={addComment}>Comment</Button>
                </div>
              </div>
            )}

            {tab === "Trace" && (
              <div className="space-y-3">
                <div>
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Incoming</p>
                  {traces.filter((t) => t.target === focus.semanticId).length === 0 && <p className="text-slate-600">none</p>}
                  {traces.filter((t) => t.target === focus.semanticId).map((t) => (
                    <div key={t.id} className="rounded border border-line bg-surface-2 p-2"><p className="text-slate-300">{t.source} <span className="text-brand-400">—{t.relation}→</span> {t.target}</p>{t.revision_context && <p className="text-[11px] text-slate-500">rev: {t.revision_context}</p>}</div>
                  ))}
                </div>
                <div>
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Outgoing</p>
                  {traces.filter((t) => t.source === focus.semanticId).length === 0 && <p className="text-slate-600">none</p>}
                  {traces.filter((t) => t.source === focus.semanticId).map((t) => (
                    <div key={t.id} className="rounded border border-line bg-surface-2 p-2"><p className="text-slate-300">{t.source} <span className="text-brand-400">—{t.relation}→</span> {t.target}</p>{t.revision_context && <p className="text-[11px] text-slate-500">rev: {t.revision_context}</p>}</div>
                  ))}
                </div>
              </div>
            )}

            {tab === "Impact" && (
              <div className="space-y-3">
                {!impact && <p className="text-slate-500">No impact data.</p>}
                {impact && (
                  <>
                    <div>
                      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Affects (downstream)</p>
                      {impact.downstream.length === 0 && <p className="text-slate-600">none</p>}
                      {impact.downstream.map((d, i) => <p key={i} className="text-slate-300">{d.semantic_id} <span className="text-slate-500">({d.relation})</span></p>)}
                    </div>
                    <div>
                      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Depends on (upstream)</p>
                      {impact.upstream.length === 0 && <p className="text-slate-600">none</p>}
                      {impact.upstream.map((u, i) => <p key={i} className="text-slate-300">{u.semantic_id} <span className="text-slate-500">({u.relation})</span></p>)}
                    </div>
                  </>
                )}
              </div>
            )}

            {tab === "History" && (
              <div className="space-y-2">
                {timeline.length === 0 && <p className="text-slate-500">No activity on this object.</p>}
                {timeline.slice().reverse().map((e, i) => (
                  <div key={i} className="rounded border border-line bg-surface-2 p-2 text-[12px]">
                    <div className="flex justify-between text-[11px] text-slate-500">
                      <span>{e.actor}</span>
                      <span>{(e.at || "").slice(0, 19).replace("T", " ")}</span>
                    </div>
                    <p className="mt-1 font-mono text-[11px] text-brand-300">{e.kind}</p>
                    <p className="text-slate-300">{e.label}</p>
                  </div>
                ))}
              </div>
            )}

            {tab === "Evidence" && (
              <div className="space-y-3">
                {evidenceAnnotations.length === 0 && (!context?.evidence || context.evidence.length === 0) && (
                  <p className="text-slate-500">No decisions, assumptions, clarifications or confirmations recorded for this object.</p>
                )}
                {evidenceAnnotations.map((a) => (
                  <div key={a.id} className="rounded border border-line bg-surface-2 p-2">
                    <p className="text-[11px] text-slate-500">{a.type} · {a.created_by}</p>
                    <p className="mt-1 text-slate-300">{a.content}</p>
                  </div>
                ))}
                {(context?.evidence || []).map((c, i) => (
                  <div key={i} className="rounded border border-line bg-surface-2 p-2">
                    <p className="text-[11px] text-slate-500">confirmation · {c.confirmed_by} · {(c.confirmed_at || "").slice(0, 19).replace("T", " ")}</p>
                    {c.comment && <p className="mt-1 text-slate-300">{c.comment}</p>}
                    {c.evidence && <pre className="mt-1 overflow-x-auto font-mono text-[11px] text-slate-400">{JSON.stringify(c.evidence, null, 2)}</pre>}
                  </div>
                ))}
              </div>
            )}

            {tab === "Help" && (
              <div className="space-y-2 text-[12px] text-slate-400">
                <p><b className="text-slate-200">What is this?</b> — the object type and display name above.</p>
                <p><b className="text-slate-200">Why is this here?</b> — read its Comments and Evidence.</p>
                <p><b className="text-slate-200">Where did it come from?</b> — Trace → Incoming.</p>
                <p><b className="text-slate-200">What uses it / what does it affect?</b> — Trace → Outgoing, and Impact.</p>
                <p><b className="text-slate-200">Who changed it, when, which revision?</b> — History.</p>
                <p><b className="text-slate-200">Is it confirmed?</b> — the status badge above.</p>
                <p className="text-slate-500">All of this is structured project data — nothing here is invented.</p>
                <Glossary />
              </div>
            )}
          </>
        )}
      </div>
    </aside>
  );
}

function Glossary() {
  const [detailed, setDetailed] = useState(false);
  return (
    <div className="mt-3 border-t border-line pt-3">
      <div className="mb-2 flex items-center justify-between">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Glossary</p>
        <button className="rounded px-2 py-0.5 text-[11px] text-brand-300 hover:bg-surface-2" onClick={() => setDetailed((d) => !d)}>
          {detailed ? "simple" : "detailed"}
        </button>
      </div>
      <dl className="space-y-1.5">
        {GLOSSARY.map((g) => (
          <div key={g.term}>
            <dt className="text-slate-200">{g.term}</dt>
            <dd className="text-[11px] text-slate-500">{detailed ? g.detailed : g.simple}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
