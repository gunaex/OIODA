import React, { useCallback, useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useWorkspace } from "../App.jsx";
import { Card, Empty, ErrorNote, Field, inputClass } from "../components/ui.jsx";

/*
 * Revision compare: text diff for UR/DR sections + semantic diff for DB
 * design payloads embedded in revision snapshots. Diffs are derived from
 * stable semantic ids, never positional comparison.
 */
const KIND_COLOR = {
  ADDED: "text-emerald-400",
  REMOVED: "text-red-400",
  CHANGED: "text-amber-400",
};

function TextDiff({ chunks }) {
  if (!chunks) return null;
  return (
    <pre className="mt-2 overflow-x-auto rounded border border-line bg-surface-0 p-2 font-mono text-[11px] leading-relaxed">
      {chunks.map((c, i) => (
        <div key={i} className={c.op === "insert" ? "bg-emerald-500/10 text-emerald-300" : c.op === "delete" ? "bg-red-500/10 text-red-300" : "text-slate-400"}>
          {c.op === "insert" ? "+ " : c.op === "delete" ? "- " : "  "}
          {c.lines.join("\n")}
        </div>
      ))}
    </pre>
  );
}

export function Compare() {
  const { project } = useWorkspace();
  const [type, setType] = useState("UR");
  const [artifacts, setArtifacts] = useState([]);
  const [artifact, setArtifact] = useState(null);
  const [revisions, setRevisions] = useState([]);
  const [aId, setAId] = useState("");
  const [bId, setBId] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const loadArtifacts = useCallback(() => {
    if (!project) return;
    api.get(`/projects/${project.id}/artifacts`).then((rows) => {
      const arts = rows.filter((a) => a.type === type);
      setArtifacts(arts);
      setArtifact((prev) => arts.find((a) => a.id === prev?.id) || arts[0] || null);
    }).catch(setError);
  }, [project?.id, type]);

  useEffect(loadArtifacts, [loadArtifacts]);

  useEffect(() => {
    if (!artifact) { setRevisions([]); return; }
    api.get(`/artifacts/${artifact.id}`).then((full) => {
      setRevisions(full.revisions);
      setAId(full.revisions[0]?.id || "");
      setBId(full.revisions.at(-1)?.id || "");
    }).catch(setError);
  }, [artifact?.id]);

  useEffect(() => {
    if (aId && bId) {
      api.get(`/revisions/${aId}/diff/${bId}`).then(setResult).catch(setError);
    } else {
      setResult(null);
    }
  }, [aId, bId]);

  function changeRow(c, key) {
    return (
      <div key={key} className="rounded border border-line bg-surface-2 px-3 py-2">
        <div className="flex items-center gap-2">
          <span className={`text-[11px] font-semibold ${KIND_COLOR[c.kind] || "text-slate-400"}`}>{c.kind}</span>
          <span className="text-[11px] text-slate-500">{c.object}</span>
          <span className="font-mono text-[12px] text-brand-300">{c.semantic_id}</span>
          {c.label && <span className="text-[12px] text-slate-300">— {c.label}</span>}
          {c.attribute && (
            <span className="text-[11px] text-slate-500">
              {c.attribute}: <span className="text-red-300">{String(c.before ?? "")}</span> → <span className="text-emerald-300">{String(c.after ?? "")}</span>
            </span>
          )}
        </div>
        {c.text_diff && <TextDiff chunks={c.text_diff} />}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <ErrorNote error={error} />

      <Card title="Revision compare">
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Artifact type">
            <select className={inputClass} value={type} onChange={(e) => setType(e.target.value)}>
              <option value="UR">UR</option>
              <option value="DR">DR</option>
            </select>
          </Field>
          <Field label="Artifact">
            <select className={inputClass} value={artifact?.id || ""} onChange={(e) => setArtifact(artifacts.find((a) => a.id === e.target.value))}>
              {artifacts.map((a) => <option key={a.id} value={a.id}>{a.title}</option>)}
            </select>
          </Field>
          <Field label="From revision">
            <select className={inputClass} value={aId} onChange={(e) => setAId(e.target.value)}>
              {revisions.map((r) => <option key={r.id} value={r.id}>r{r.revision_number} ({r.status})</option>)}
            </select>
          </Field>
          <Field label="To revision">
            <select className={inputClass} value={bId} onChange={(e) => setBId(e.target.value)}>
              {revisions.map((r) => <option key={r.id} value={r.id}>r{r.revision_number} ({r.status})</option>)}
            </select>
          </Field>
        </div>
        {!artifact && <Empty>Select an artifact to compare revisions.</Empty>}
        {artifact && revisions.length < 2 && <Empty>Need at least two revisions to compare.</Empty>}
      </Card>

      {result && (
        <>
          <Card title={`Document diff (r${result.a.revision_number} → r${result.b.revision_number})`}>
            {result.document_diff.length === 0 && <Empty>No section-level changes.</Empty>}
            <div className="space-y-2">
              {result.document_diff.map((c, i) => changeRow(c, `d${i}`))}
            </div>
          </Card>

          <Card title="Semantic DB diff (stable object ids)">
            {result.database_diff.length === 0 && <Empty>No DB design changes between these revisions.</Empty>}
            <div className="space-y-2">
              {result.database_diff.map((c, i) => changeRow(c, `b${i}`))}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}