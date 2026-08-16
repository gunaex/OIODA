import React, { useCallback, useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useWorkspace } from "../App.jsx";
import { Button, Card, Empty, ErrorNote, Field, inputClass } from "../components/ui.jsx";

/*
 * Project-memory surfaces for Decision / Assumption / Clarification.
 * Each record is a semantic object (DEC-…, ASM-…, CLR-…) so traces and
 * comments anchor to it; related semantic objects are recorded as
 * REFERENCES trace links.
 */
export function Decisions() {
  const { project, setFocus } = useWorkspace();
  const [memory, setMemory] = useState({ decisions: [], assumptions: [], clarifications: [] });
  const [tab, setTab] = useState("decisions");
  const [error, setError] = useState(null);

  // decision form
  const [dTitle, setDTitle] = useState("");
  const [dContent, setDContent] = useState("");
  const [dRelated, setDRelated] = useState("");
  // assumption form
  const [aContent, setAContent] = useState("");
  // clarification form
  const [cQuestion, setCQuestion] = useState("");
  const [cAnswer, setCAnswer] = useState("");

  const load = useCallback(() => {
    if (project) api.get(`/projects/${project.id}/project-memory`).then(setMemory).catch(setError);
  }, [project?.id]);
  useEffect(load, [load]);

  const ids = (s) => s.split(/[\s,]+/).filter(Boolean);

  async function addDecision(e) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/decisions", { project_id: project.id, title: dTitle, content: dContent, related_semantic_ids: ids(dRelated) });
      setDTitle(""); setDContent(""); setDRelated("");
      load();
    } catch (err) { setError(err); }
  }

  async function addAssumption(e) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/assumptions", { project_id: project.id, content: aContent });
      setAContent("");
      load();
    } catch (err) { setError(err); }
  }

  async function addClarification(e) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/clarifications", { project_id: project.id, question: cQuestion, answer: cAnswer || null });
      setCQuestion(""); setCAnswer("");
      load();
    } catch (err) { setError(err); }
  }

  return (
    <div className="space-y-4">
      <ErrorNote error={error} />
      <Card title="Project memory — decisions, assumptions, clarifications">
        <div className="mb-3 flex gap-1 border-b border-line pb-2">
          {[["decisions", "Decisions"], ["assumptions", "Assumptions"], ["clarifications", "Clarifications"]].map(([k, label]) => (
            <button key={k} onClick={() => setTab(k)} className={`rounded px-3 py-1 text-[13px] ${tab === k ? "bg-brand-600/20 text-brand-100" : "text-slate-400 hover:bg-surface-2"}`}>{label}</button>
          ))}
        </div>

        {tab === "decisions" && (
          <>
            {memory.decisions.length === 0 && <Empty>No decisions recorded.</Empty>}
            <ul className="space-y-2">
              {memory.decisions.map((d) => (
                <li key={d.id} className="rounded border border-line bg-surface-2 p-3">
                  <div className="flex items-center justify-between">
                    <button className="font-mono text-[13px] text-brand-300 hover:text-brand-100" onClick={() => setFocus(d.code, d.code)}>{d.code}</button>
                    <span className="text-[11px] text-slate-500">by {d.decided_by} · {(d.decided_at || "").slice(0, 19).replace("T", " ")}</span>
                  </div>
                  <p className="mt-1 text-[13px] text-slate-200">{d.title}</p>
                  <p className="text-[12px] text-slate-400">{d.content}</p>
                  {d.related.length > 0 && <p className="mt-1 text-[11px] text-slate-500">related: {d.related.join(", ")}</p>}
                </li>
              ))}
            </ul>
            <form onSubmit={addDecision} className="mt-4 space-y-2 border-t border-line pt-3">
              <div className="grid grid-cols-2 gap-2">
                <Field label="Title"><input className={inputClass} value={dTitle} onChange={(e) => setDTitle(e.target.value)} required /></Field>
                <Field label="Related semantic IDs"><input className={inputClass} value={dRelated} onChange={(e) => setDRelated(e.target.value)} placeholder="REQ-0001, dr section" /></Field>
              </div>
              <Field label="Decision"><textarea className={`${inputClass} min-h-16 w-full`} value={dContent} onChange={(e) => setDContent(e.target.value)} required /></Field>
              <Button variant="primary" disabled={!dTitle || !dContent}>Record decision</Button>
            </form>
          </>
        )}

        {tab === "assumptions" && (
          <>
            {memory.assumptions.length === 0 && <Empty>No assumptions.</Empty>}
            <ul className="space-y-2">
              {memory.assumptions.map((a) => (
                <li key={a.id} className="rounded border border-line bg-surface-2 p-3">
                  <div className="flex items-center justify-between">
                    <button className="font-mono text-[13px] text-brand-300 hover:text-brand-100" onClick={() => setFocus(a.code, a.code)}>{a.code}</button>
                    <span className="text-[11px] text-slate-500">{a.status} · by {a.created_by}</span>
                  </div>
                  <p className="mt-1 text-[13px] text-slate-200">{a.content}</p>
                </li>
              ))}
            </ul>
            <form onSubmit={addAssumption} className="mt-4 space-y-2 border-t border-line pt-3">
              <Field label="Assumption"><textarea className={`${inputClass} min-h-16 w-full`} value={aContent} onChange={(e) => setAContent(e.target.value)} required /></Field>
              <Button variant="primary" disabled={!aContent}>Record assumption</Button>
            </form>
          </>
        )}

        {tab === "clarifications" && (
          <>
            {memory.clarifications.length === 0 && <Empty>No clarifications.</Empty>}
            <ul className="space-y-2">
              {memory.clarifications.map((c) => (
                <li key={c.id} className="rounded border border-line bg-surface-2 p-3">
                  <div className="flex items-center justify-between">
                    <button className="font-mono text-[13px] text-brand-300 hover:text-brand-100" onClick={() => setFocus(c.code, c.code)}>{c.code}</button>
                    <span className="text-[11px] text-slate-500">{c.resolved ? "resolved" : "open"} · by {c.asked_by}</span>
                  </div>
                  <p className="mt-1 text-[13px] text-slate-200">Q: {c.question}</p>
                  {c.answer && <p className="text-[12px] text-slate-400">A: {c.answer}</p>}
                </li>
              ))}
            </ul>
            <form onSubmit={addClarification} className="mt-4 space-y-2 border-t border-line pt-3">
              <Field label="Question"><input className={inputClass} value={cQuestion} onChange={(e) => setCQuestion(e.target.value)} required /></Field>
              <Field label="Answer (optional)"><input className={inputClass} value={cAnswer} onChange={(e) => setCAnswer(e.target.value)} /></Field>
              <Button variant="primary" disabled={!cQuestion}>Record clarification</Button>
            </form>
          </>
        )}
      </Card>
    </div>
  );
}