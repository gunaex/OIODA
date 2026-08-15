import React, { useCallback, useEffect, useRef, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import { StarterKit } from "@tiptap/starter-kit";
import { Table, TableRow, TableCell, TableHeader } from "@tiptap/extension-table";
import { Link } from "@tiptap/extension-link";
import { TaskList } from "@tiptap/extension-task-list";
import { TaskItem } from "@tiptap/extension-task-item";
import { api } from "../api/client.js";
import { useWorkspace } from "../App.jsx";
import { Button, Card, ConfirmDialog, Empty, ErrorNote, Field, StatusBadge, inputClass } from "../components/ui.jsx";

/*
 * Rich UR/DR document workspace (P2).
 *
 * Content model — the structured JSON is the source of truth, never the
 * rendered HTML:
 *   snapshot.sections = [
 *     { id, heading, content: <ProseMirror doc JSON>, plain_text }
 *   ]
 *
 * Section `id` is a stable semantic id (docsec_<artifact>_<n>) registered
 * as a DOCUMENT_SECTION semantic object. Editing the heading/body never
 * changes the semantic identity. Confirmed revisions are read-only.
 */

const EMPTY_DOC = { type: "doc", content: [{ type: "paragraph" }] };

function newSectionId(artifactId, n) {
  return `docsec_${artifactId}_${n}_${Math.random().toString(36).slice(2, 7)}`;
}

function emptyDocument() {
  return [{ id: `docsec_${Math.random().toString(36).slice(2, 10)}`, heading: "Overview", content: EMPTY_DOC, plain_text: "Overview\n" }];
}

/* ------------------------------------------------------------------ */
/* Tiptap section editor                                               */
/* ------------------------------------------------------------------ */

function Toolbar({ editor, editable }) {
  if (!editor || !editable) return null;
  const B = ({ onClick, active, children, title }) => (
    <button
      type="button"
      title={title}
      onMouseDown={(e) => e.preventDefault()}
      onClick={onClick}
      className={`rounded px-1.5 py-0.5 text-[12px] ${active ? "bg-brand-600/30 text-brand-100" : "text-slate-400 hover:bg-surface-2 hover:text-slate-200"}`}
    >
      {children}
    </button>
  );
  const addLink = () => {
    const href = window.prompt("Link URL");
    if (href === null) return;
    editor.chain().focus().extendMarkRange("link").setLink({ href }).run();
  };
  return (
    <div className="flex flex-wrap items-center gap-0.5 border-b border-line bg-surface-2 px-1 py-1">
      <B title="Heading 2" active={editor.isActive("heading", { level: 2 })} onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}>H2</B>
      <B title="Heading 3" active={editor.isActive("heading", { level: 3 })} onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}>H3</B>
      <B title="Bold" active={editor.isActive("bold")} onClick={() => editor.chain().focus().toggleBold().run()}><b>B</b></B>
      <B title="Italic" active={editor.isActive("italic")} onClick={() => editor.chain().focus().toggleItalic().run()}><i>I</i></B>
      <B title="Bullet list" active={editor.isActive("bulletList")} onClick={() => editor.chain().focus().toggleBulletList().run()}>• list</B>
      <B title="Numbered list" active={editor.isActive("orderedList")} onClick={() => editor.chain().focus().toggleOrderedList().run()}>1. list</B>
      <B title="Task list" active={editor.isActive("taskList")} onClick={() => editor.chain().focus().toggleTaskList().run()}>☑ list</B>
      <B title="Code block" active={editor.isActive("codeBlock")} onClick={() => editor.chain().focus().toggleCodeBlock().run()}>{"</>"}</B>
      <B title="Blockquote" active={editor.isActive("blockquote")} onClick={() => editor.chain().focus().toggleBlockquote().run()}>❝</B>
      <B title="Link" active={editor.isActive("link")} onClick={addLink}>🔗</B>
      <B title="Insert table" onClick={() => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}>⊞ table</B>
    </div>
  );
}

function SectionEditor({ section, editable, onChange }) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Table.configure({ resizable: false }),
      TableRow,
      TableCell,
      TableHeader,
      Link.configure({ openOnClick: false }),
      TaskList,
      TaskItem.configure({ nested: true }),
    ],
    content: section.content || EMPTY_DOC,
    editable,
    onUpdate: ({ editor }) => {
      onChange({ ...section, content: editor.getJSON(), plain_text: `${section.heading || ""}\n${editor.getText()}` });
    },
  });

  useEffect(() => {
    if (editor) editor.setEditable(!!editable);
  }, [editor, editable]);

  return (
    <div className="overflow-hidden rounded border border-line">
      <Toolbar editor={editor} editable={editable} />
      <div className="p-3">
        <EditorContent
          editor={editor}
          className="prose prose-invert max-w-none text-[13px] text-slate-200 [&_h1]:text-xl [&_h2]:text-lg [&_h3]:text-base [&_p]:my-1.5 [&_ul]:list-disc [&_ol]:list-decimal [&_ul]:pl-5 [&_ol]:pl-5 [&_pre]:rounded [&_pre]:bg-surface-0 [&_pre]:p-2 [&_pre]:font-mono [&_pre]:text-[12px] [&_blockquote]:border-l-2 [&_blockquote]:border-line [&_blockquote]:pl-3 [&_blockquote]:text-slate-400 [&_table]:w-full [&_table]:border [&_table]:border-line [&_th]:border [&_th]:border-line [&_th]:bg-surface-2 [&_th]:p-1 [&_td]:border [&_td]:border-line [&_td]:p-1 [&_ul[data-type='taskList']]:list-none [&_ul[data-type='taskList']]:pl-0"
        />
      </div>
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
  const [saving, setSaving] = useState("idle");
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const saveTimer = useRef(null);

  const loadArtifacts = useCallback(() => {
    if (!project) return;
    api.get(`/projects/${project.id}/artifacts`).then((rows) => setArtifacts(rows.filter((a) => a.type === type))).catch(setError);
  }, [project?.id, type]);

  useEffect(loadArtifacts, [loadArtifacts]);
  useEffect(() => () => clearTimeout(saveTimer.current), []);

  const loadDoc = useCallback((revisionId) => {
    if (!revisionId) return;
    api.get(`/revisions/${revisionId}/document`).then((d) => setDoc(d)).catch(setError);
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
      const created = await api.post("/artifacts", { project_id: project.id, type, title, snapshot: { sections: emptyDocument() } });
      setTitle("");
      loadArtifacts();
      openArtifact(created);
    } catch (err) { setError(err); }
  }

  /* -------- editing + debounced autosave -------- */

  const doSave = useCallback(async (sections) => {
    if (!doc || !doc.editable) return;
    setSaving("saving");
    try {
      await api.put(`/revisions/${doc.revision_id}/document`, { sections });
      setSaving("saved");
      setTimeout(() => setSaving((s) => (s === "saved" ? "idle" : s)), 1200);
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

  function updateSection(id, patch) {
    mutateSections((sections) => sections.map((s) => (s.id === id ? { ...s, ...patch } : s)));
  }

  function addSection() {
    mutateSections((sections) => [...sections, { id: newSectionId(selectedArtifactId, sections.length + 1), heading: `Section ${sections.length + 1}`, content: EMPTY_DOC, plain_text: "" }]);
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

  /* -------- lifecycle -------- */

  async function lifecycle(path) {
    setError(null);
    try {
      await api.post(path);
      if (selectedArtifactId) {
        const full = await api.get(`/artifacts/${selectedArtifactId}`);
        setRevisions(full.revisions);
        const current = full.revisions.find((r) => r.id === full.current_draft_revision_id) || full.revisions.at(-1);
        if (current) loadDoc(current.id);
      }
      loadArtifacts();
    } catch (err) { setError(err); }
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
    } catch (err) { setError(err); }
  }

  async function confirm({ comment, evidence }) {
    setError(null);
    setBusy(true);
    try {
      await api.post(`/revisions/${doc.revision_id}/confirm`, { comment, evidence });
      setConfirming(false);
      const full = await api.get(`/artifacts/${selectedArtifactId}`);
      setRevisions(full.revisions);
      loadDoc(doc.revision_id);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const editable = doc?.editable;
  const savingLabel = { idle: "saved", dirty: "unsaved changes", saving: "saving…", saved: "saved ✓" }[saving];

  return (
    <div className="grid grid-cols-[260px_1fr] gap-4">
      {/* Sidebar */}
      <div className="space-y-3">
        <Card title={`${type} artifacts`}>
          {artifacts.length === 0 && <Empty>None yet.</Empty>}
          <ul className="space-y-1">
            {artifacts.map((a) => (
              <li key={a.id}>
                <button onClick={() => openArtifact(a)} className={`w-full rounded px-2 py-1.5 text-left text-[13px] ${selectedArtifactId === a.id ? "bg-brand-600/20 text-brand-100" : "text-slate-300 hover:bg-surface-2"}`}>{a.title}</button>
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
                  <button onClick={() => loadDoc(r.id)} className={`flex w-full items-center justify-between rounded px-2 py-1.5 text-[12px] ${doc.revision_id === r.id ? "bg-surface-2 text-slate-200" : "text-slate-400 hover:bg-surface-2"}`}>
                    <span>r{r.revision_number}</span>
                    <StatusBadge status={r.status} />
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>

      {/* Editor */}
      <div className="space-y-3">
        <ErrorNote error={error} />
        {!doc && <Card title="Document"><Empty>Select or create a {type} artifact.</Empty></Card>}

        {doc && (
          <>
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
                {editable && <Button onClick={() => doSave(doc.sections)}>Save checkpoint</Button>}
                <StatusBadge status={doc.status} />
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {doc.status === "DRAFT" && (
                <Button variant="primary" onClick={() => lifecycle(`/revisions/${doc.revision_id}/submit-for-review`)}>Submit for review</Button>
              )}
              {doc.status === "IN_REVIEW" && (
                <>
                  <Button variant="primary" onClick={() => setConfirming(true)}>Confirm…</Button>
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
                  <div key={s.id} className="flex items-center gap-1">
                    <button onClick={() => document.getElementById(`section-${s.id}`)?.scrollIntoView({ behavior: "smooth" })} className="block w-full rounded px-2 py-1 text-left text-[12px] text-slate-400 hover:bg-surface-2">
                      <span className="text-slate-600">{i + 1}.</span> {s.heading || "Untitled"}
                    </button>
                    {editable && (
                      <>
                        <button className="text-[11px] text-slate-600 hover:text-slate-300" onClick={() => moveSection(s.id, -1)}>↑</button>
                        <button className="text-[11px] text-slate-600 hover:text-slate-300" onClick={() => moveSection(s.id, 1)}>↓</button>
                        <button className="text-[11px] text-slate-600 hover:text-red-400" onClick={() => removeSection(s.id)}>✕</button>
                      </>
                    )}
                  </div>
                ))}
                {editable && <button onClick={addSection} className="mt-2 w-full rounded px-2 py-1 text-left text-[12px] text-brand-300 hover:bg-surface-2">+ section</button>}
              </div>

              {/* Sections */}
              <div className="space-y-4">
                {doc.sections.map((s) => (
                  <div key={s.id} id={`section-${s.id}`} className="rounded-lg border border-line bg-surface-1 p-4">
                    <div className="mb-2 flex items-center gap-2">
                      <input className="flex-1 bg-transparent text-[15px] font-semibold text-slate-100 outline-none" value={s.heading || ""} disabled={!editable} placeholder="Section heading" onChange={(e) => updateSection(s.id, { heading: e.target.value })} />
                      <span className="font-mono text-[10px] text-slate-600">{s.id}</span>
                    </div>
                    <SectionEditor
                      key={`${doc.revision_id}:${s.id}`}
                      section={s}
                      editable={editable}
                      onChange={(updated) => updateSection(s.id, updated)}
                    />
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

      <ConfirmDialog
        open={confirming}
        revision={doc ? { id: doc.revision_id, revision_number: doc.revision_number, artifact_title: doc.title } : undefined}
        onClose={() => setConfirming(false)}
        onConfirm={confirm}
        busy={busy}
        error={error}
      />
    </div>
  );
}