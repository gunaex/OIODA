import React, { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client.js";
import { useWorkspace } from "../App.jsx";
import { Button, Card, Empty, ErrorNote, Field, StatusBadge, inputClass } from "../components/ui.jsx";

/*
 * Rich UR/DR document workspace.
 *
 * Content model (stored in the revision snapshot):
 *   snapshot.sections = [{ id, heading, blocks: [{kind, ...}] }]
 *
 * Section `id` is a stable semantic id (docsec_<artifact>_<n>) — the
 * backend registers it as a DOCUMENT_SECTION semantic object so comments
 * and traces bind to the section, never to a DOM position.
 *
 * Confirmed revisions are read-only: the backend rejects edits (409) and
 * this editor also disables them client-side.
 */

function newBlock(kind) {
  switch (kind) {
    case "heading": return { kind, level: 2, text: "" };
    case "bullet_list": return { kind, items: [""] };
    case "numbered_list": return { kind, items: [""] };
    case "table": return { kind, header: ["Column"], rows: [[""]] };
    case "code": return { kind, lang: "text", text: "" };
    default: return { kind: "paragraph", text: "" };
  }
}

function emptyDocument() {
  return [{ id: `docsec_${Math.random().toString(36).slice(2, 10)}`, heading: "Overview", blocks: [{ kind: "paragraph", text: "" }] }];
}

function newSectionId(artifactId, n) {
  return `docsec_${artifactId}_${n}_${Math.random().toString(36).slice(2, 7)}`;
}

/* ------------------------------------------------------------------ */
/* Block editor                                                        */
/* ------------------------------------------------------------------ */

function BlockEditor({ block, editable, onChange }) {
  const set = (patch) => onChange({ ...block, ...patch });

  if (block.kind === "heading") {
    return (
      <div className="flex items-center gap-2">
        <select
          className="rounded border border-line bg-surface-0 px-1 py-0.5 text-[12px] text-slate-300"
          value={block.level || 2}
          disabled={!editable}
          onChange={(e) => set({ level: Number(e.target.value) })}
        >
          <option value={2}>H2</option>
          <option value={3}>H3</option>
          <option value={4}>H4</option>
        </select>
        <input
          className={`${inputClass} flex-1 text-[15px] font-semibold`}
          value={block.text || ""}
          disabled={!editable}
          placeholder="Heading"
          onChange={(e) => set({ text: e.target.value })}
        />
      </div>
    );
  }

  if (block.kind === "paragraph") {
    return (
      <textarea
        className={`${inputClass} min-h-16 w-full leading-relaxed`}
        value={block.text || ""}
        disabled={!editable}
        placeholder="Write a paragraph…"
        onChange={(e) => set({ text: e.target.value })}
      />
    );
  }

  if (block.kind === "bullet_list" || block.kind === "numbered_list") {
    const items = block.items || [""];
    const ordered = block.kind === "numbered_list";
    return (
      <div className="space-y-1 pl-1">
        {items.map((item, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="w-5 text-right text-[12px] text-slate-500">{ordered ? `${i + 1}.` : "•"}</span>
            <input
              className={`${inputClass} flex-1`}
              value={item}
              disabled={!editable}
              onChange={(e) => {
                const next = [...items];
                next[i] = e.target.value;
                set({ items: next });
              }}
            />
            {editable && items.length > 1 && (
              <button className="text-[12px] text-slate-500 hover:text-red-400" onClick={() => set({ items: items.filter((_, j) => j !== i) })}>✕</button>
            )}
          </div>
        ))}
        {editable && (
          <button className="ml-6 text-[12px] text-brand-300 hover:text-brand-100" onClick={() => set({ items: [...items, ""] })}>
            + add item
          </button>
        )}
      </div>
    );
  }

  if (block.kind === "table") {
    const header = block.header || [""];
    const rows = block.rows || [];
    const setCell = (r, c, val) => {
      if (r === -1) {
        const next = [...header];
        next[c] = val;
        set({ header: next });
      } else {
        const next = rows.map((row) => [...row]);
        next[r][c] = val;
        set({ rows: next });
      }
    };
    return (
      <div className="overflow-x-auto">
        <table className="w-full border border-line text-[13px]">
          <thead>
            <tr>
              {header.map((h, c) => (
                <th key={c} className="border border-line bg-surface-2 p-1">
                  <input className="w-full bg-transparent px-1 font-semibold outline-none" value={h} disabled={!editable} onChange={(e) => setCell(-1, c, e.target.value)} />
                </th>
              ))}
              {editable && (
                <th className="w-8 border border-line bg-surface-2 p-1 text-center">
                  <button className="text-slate-500 hover:text-brand-300" title="Add column" onClick={() => set({ header: [...header, "Column"], rows: rows.map((r) => [...r, ""]) })}>+</button>
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, r) => (
              <tr key={r}>
                {row.map((cell, c) => (
                  <td key={c} className="border border-line p-1">
                    <input className="w-full bg-transparent px-1 outline-none" value={cell} disabled={!editable} onChange={(e) => setCell(r, c, e.target.value)} />
                  </td>
                ))}
                {editable && (
                  <td className="w-8 border border-line p-1 text-center">
                    <button className="text-slate-500 hover:text-red-400" title="Remove row" onClick={() => set({ rows: rows.filter((_, j) => j !== r) })}>✕</button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        {editable && (
          <button className="mt-1 text-[12px] text-brand-300 hover:text-brand-100" onClick={() => set({ rows: [...rows, header.map(() => "")] })}>+ add row</button>
        )}
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between rounded-t border border-line border-b-0 bg-surface-2 px-2 py-1">
        <span className="text-[11px] uppercase tracking-wider text-slate-500">{block.lang || "text"}</span>
      </div>
      <textarea
        className="min-h-24 w-full rounded-b border border-line bg-surface-0 px-3 py-2 font-mono text-[12px] leading-relaxed text-slate-200 outline-none"
        value={block.text || ""}
        disabled={!editable}
        spellCheck={false}
        placeholder="code / preformatted"
        onChange={(e) => set({ text: e.target.value })}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main document workspace                                             */
/* ------------------------------------------------------------------ */

export function Artifacts({ type }) {
  const { project, setFocus } = useWorkspace();
  const [artifacts, setArtifacts] = useState([]);
  const [selectedArtifactId, setSelectedArtifactId] = useState(null);
  const [revisions, setRevisions] = useState([]);
  const [doc, setDoc] = useState(null);
  const [error, setError] = useState(null);
  const [title, setTitle] = useState("");
  const [saving, setSaving] = useState("idle"); // idle | dirty | saving | saved
  const [activeSection, setActiveSection] = useState(null);
  const saveTimer = useRef(null);

  const loadArtifacts = useCallback(() => {
    if (!project) return;
    api.get(`/projects/${project.id}/artifacts`)
      .then((rows) => setArtifacts(rows.filter((a) => a.type === type)))
      .catch(setError);
  }, [project?.id, type]);

  useEffect(loadArtifacts, [loadArtifacts]);
  useEffect(() => () => clearTimeout(saveTimer.current), []);

  const loadDoc = useCallback((revisionId) => {
    if (!revisionId) return;
    api.get(`/revisions/${revisionId}/document`).then((d) => {
      setDoc(d);
      setActiveSection(d.sections?.[0]?.id || null);
    }).catch(setError);
  }, []);

  function openArtifact(a) {
    setSelectedArtifactId(a.id);
    api.get(`/artifacts/${a.id}`).then((full) => {
      setRevisions(full.revisions);
      const current = full.revisions.find((r) => r.id === full.current_draft_revision_id) || full.revisions.at(-1);
      if (current) {
        loadDoc(current.id);
        setFocus(`sec_${current.id}`, `${type} r${current.revision_number}`);
      }
    }).catch(setError);
  }

  async function createArtifact(e) {
    e.preventDefault();
    setError(null);
    try {
      const created = await api.post("/artifacts", {
        project_id: project.id, type, title,
        snapshot: { sections: emptyDocument() },
      });
      setTitle("");
      loadArtifacts();
      openArtifact(created);
    } catch (err) {
      setError(err);
    }
  }

  /* -------- content editing (local + debounced autosave) -------- */

  const doSave = useCallback(async (sections) => {
    if (!doc || !doc.editable) return;
    setSaving("saving");
    try {
      const updated = await api.put(`/revisions/${doc.revision_id}/document`, { sections });
      setDoc((d) => ({ ...d, ...updated, sections: updated.sections }));
      setSaving("saved");
      setTimeout(() => setSaving((s) => (s === "saved" ? "idle" : s)), 1500);
    } catch (err) {
      setError(err);
      setSaving("dirty");
    }
  }, [doc]);

  function mutateSections(fn) {
    if (!doc || !doc.editable) return;
    setSaving("dirty");
    const next = fn(doc.sections);
    setDoc((d) => ({ ...d, sections: next }));
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => doSave(next), 900);
  }

  /* -------- section helpers -------- */

  function updateSection(id, patch) {
    mutateSections((sections) => sections.map((s) => (s.id === id ? { ...s, ...patch } : s)));
  }

  function addSection() {
    mutateSections((sections) => [
      ...sections,
      { id: newSectionId(selectedArtifactId, sections.length + 1), heading: `Section ${sections.length + 1}`, blocks: [{ kind: "paragraph", text: "" }] },
    ]);
  }

  function removeSection(id) {
    mutateSections((sections) => sections.filter((s) => s.id !== id));
  }

  function moveSection(id, dir) {
    mutateSections((sections) => {
      const i = sections.findIndex((s) => s.id === id);
      const j = i + dir;
      if (i < 0 || j < 0 || j >= sections.length) return sections;
      const next = [...sections];
      [next[i], next[j]] = [next[j], next[i]];
      return next;
    });
  }

  function updateBlock(sectionId, blockIdx, block) {
    mutateSections((sections) => sections.map((s) => {
      if (s.id !== sectionId) return s;
      const blocks = [...s.blocks];
      blocks[blockIdx] = block;
      return { ...s, blocks };
    }));
  }

  function addBlock(sectionId, kind) {
    mutateSections((sections) => sections.map((s) => (s.id === sectionId ? { ...s, blocks: [...s.blocks, newBlock(kind)] } : s)));
  }

  function removeBlock(sectionId, blockIdx) {
    mutateSections((sections) => sections.map((s) => (s.id === sectionId ? { ...s, blocks: s.blocks.filter((_, i) => i !== blockIdx) } : s)));
  }

  /* -------- lifecycle -------- */

  async function lifecycle(path, body) {
    setError(null);
    try {
      await api.post(path, body);
      if (selectedArtifactId) {
        const full = await api.get(`/artifacts/${selectedArtifactId}`);
        setRevisions(full.revisions);
        const current = full.revisions.find((r) => r.id === full.current_draft_revision_id) || full.revisions.at(-1);
        if (current) loadDoc(current.id);
      }
      loadArtifacts();
    } catch (err) {
      setError(err);
    }
  }

  async function clone(revision) {
    setError(null);
    try {
      const created = await api.post(`/artifacts/${selectedArtifactId}/revisions`, { based_on_revision_id: revision.id });
      if (selectedArtifactId) {
        const full = await api.get(`/artifacts/${selectedArtifactId}`);
        setRevisions(full.revisions);
      }
      loadDoc(created.id);
      loadArtifacts();
    } catch (err) {
      setError(err);
    }
  }

  const editable = doc?.editable;
  const savingLabel = { idle: "saved", dirty: "unsaved changes", saving: "saving…", saved: "saved ✓" }[saving];

  return (
    <div className="grid grid-cols-[260px_1fr] gap-4">
      {/* Artifact + revision sidebar */}
      <div className="space-y-3">
        <Card title={`${type} artifacts`}>
          {artifacts.length === 0 && <Empty>None yet.</Empty>}
          <ul className="space-y-1">
            {artifacts.map((a) => (
              <li key={a.id}>
                <button
                  onClick={() => openArtifact(a)}
                  className={`w-full rounded px-2 py-1.5 text-left text-[13px] ${
                    selectedArtifactId === a.id ? "bg-brand-600/20 text-brand-100" : "text-slate-300 hover:bg-surface-2"
                  }`}
                >
                  {a.title}
                </button>
              </li>
            ))}
          </ul>
          <form onSubmit={createArtifact} className="mt-4 space-y-2 border-t border-line pt-3">
            <Field label={`New ${type}`}>
              <input className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} required />
            </Field>
            <Button variant="primary" disabled={!title}>Create {type}</Button>
          </form>
        </Card>

        {doc && (
          <Card title="Revisions">
            <ul className="space-y-1">
              {revisions.map((r) => (
                <li key={r.id}>
                  <button
                    onClick={() => loadDoc(r.id)}
                    className={`flex w-full items-center justify-between rounded px-2 py-1.5 text-[12px] ${
                      doc.revision_id === r.id ? "bg-surface-2 text-slate-200" : "text-slate-400 hover:bg-surface-2"
                    }`}
                  >
                    <span>r{r.revision_number}</span>
                    <StatusBadge status={r.status} />
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>

      {/* Document editor */}
      <div className="space-y-3">
        <ErrorNote error={error} />

        {!doc && <Card title="Document"><Empty>Select or create a {type} artifact.</Empty></Card>}

        {doc && (
          <>
            {/* Revision context header */}
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line bg-surface-1 px-4 py-3">
              <div className="flex items-center gap-3">
                <span className="rounded bg-brand-600 px-2 py-0.5 text-[12px] font-bold text-white">{type}</span>
                <div>
                  <p className="text-[14px] font-semibold text-slate-200">{doc.title}</p>
                  <p className="text-[11px] text-slate-500">
                    r{doc.revision_number} · {doc.artifact_type} · based on {doc.based_on_revision_id ? "…" + doc.based_on_revision_id.slice(-6) : "—"} · by {doc.created_by}
                    {doc.confirmed_by ? ` · confirmed by ${doc.confirmed_by}` : ""}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-[11px] ${saving === "dirty" ? "text-amber-400" : saving === "saving" ? "text-slate-400" : "text-slate-600"}`}>{savingLabel}</span>
                {editable && <Button onClick={() => doSave(doc.sections)}>Save</Button>}
                <StatusBadge status={doc.status} />
              </div>
            </div>

            {/* Lifecycle actions */}
            <div className="flex flex-wrap items-center gap-2">
              {doc.status === "DRAFT" && (
                <Button variant="primary" onClick={() => lifecycle(`/revisions/${doc.revision_id}/submit-for-review`)}>Submit for review</Button>
              )}
              {doc.status === "IN_REVIEW" && (
                <>
                  <Button variant="primary" onClick={() => lifecycle(`/revisions/${doc.revision_id}/confirm`, { comment: "Confirmed from workspace", evidence: { surface: "document" } })}>Confirm</Button>
                  <Button onClick={() => lifecycle(`/revisions/${doc.revision_id}/return-to-draft`)}>Return to draft</Button>
                </>
              )}
              {(doc.status === "CONFIRMED" || doc.status === "SUPERSEDED") && (
                <Button onClick={() => clone({ id: doc.revision_id })}>Clone as new revision</Button>
              )}
              {!editable && doc.status === "CONFIRMED" && (
                <span className="text-[11px] text-slate-500">CONFIRMED revision is immutable — clone to evolve.</span>
              )}
            </div>

            <div className="grid grid-cols-[200px_1fr] gap-4">
              {/* Section navigation */}
              <div className="space-y-1 self-start rounded-lg border border-line bg-surface-1 p-2">
                <p className="px-2 pb-1 pt-1 text-[10px] font-semibold uppercase tracking-widest text-slate-600">Sections</p>
                {doc.sections.map((s, i) => (
                  <button
                    key={s.id}
                    onClick={() => setActiveSection(s.id)}
                    className={`block w-full rounded px-2 py-1 text-left text-[12px] ${
                      activeSection === s.id ? "bg-brand-600/20 text-brand-100" : "text-slate-400 hover:bg-surface-2"
                    }`}
                  >
                    <span className="text-slate-600">{i + 1}.</span> {s.heading || "Untitled"}
                  </button>
                ))}
                {editable && (
                  <button onClick={addSection} className="mt-2 w-full rounded px-2 py-1 text-left text-[12px] text-brand-300 hover:bg-surface-2">+ section</button>
                )}
              </div>

              {/* Sections */}
              <div className="space-y-4">
                {doc.sections.map((s, si) => (
                  <div key={s.id} id={s.id} className="rounded-lg border border-line bg-surface-1 p-4">
                    <div className="mb-3 flex items-center gap-2">
                      <input
                        className="flex-1 bg-transparent text-[15px] font-semibold text-slate-100 outline-none"
                        value={s.heading || ""}
                        disabled={!editable}
                        placeholder="Section heading"
                        onChange={(e) => updateSection(s.id, { heading: e.target.value })}
                      />
                      <span className="font-mono text-[10px] text-slate-600">{s.id}</span>
                      {editable && (
                        <>
                          <button className="text-[12px] text-slate-500 hover:text-slate-300" title="Move up" onClick={() => moveSection(s.id, -1)}>↑</button>
                          <button className="text-[12px] text-slate-500 hover:text-slate-300" title="Move down" onClick={() => moveSection(s.id, 1)}>↓</button>
                          <button className="text-[12px] text-slate-500 hover:text-red-400" title="Remove section" onClick={() => removeSection(s.id)}>✕</button>
                        </>
                      )}
                    </div>

                    <div className="space-y-2">
                      {s.blocks.map((b, bi) => (
                        <div key={bi} className="group relative">
                          <BlockEditor block={b} editable={editable} onChange={(nb) => updateBlock(s.id, bi, nb)} />
                          {editable && (
                            <button
                              className="absolute -right-1 -top-1 hidden rounded bg-surface-3 px-1 text-[11px] text-slate-500 group-hover:block hover:text-red-400"
                              onClick={() => removeBlock(s.id, bi)}
                            >✕</button>
                          )}
                        </div>
                      ))}
                    </div>

                    {editable && (
                      <div className="mt-3 flex flex-wrap gap-1 border-t border-line pt-2">
                        {["paragraph", "heading", "bullet_list", "numbered_list", "table", "code"].map((k) => (
                          <button key={k} className="rounded border border-line px-2 py-0.5 text-[11px] text-slate-400 hover:bg-surface-2 hover:text-slate-200" onClick={() => addBlock(s.id, k)}>
                            + {k.replace("_", " ")}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ))}

                {doc.sections.length === 0 && editable && (
                  <button className="rounded border border-dashed border-line p-4 text-[13px] text-slate-500 hover:bg-surface-1" onClick={addSection}>+ add first section</button>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
