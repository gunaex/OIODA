import { useEffect, useState } from "react";
import { pmApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, Loading, Empty, SignInPrompt, Table, Tr, Td, formatDateTime } from "../components/ui";

export default function PmNotesPage() {
  const { pm, pmAuthed } = useProjectCtx();
  const [notes, setNotes] = useState(null);
  const [pages, setPages] = useState([]);
  const [form, setForm] = useState("");
  const [error, setError] = useState(null);

  function load() {
    if (!pm?.slug) return;
    pmApi.notes(pm.slug).then(setNotes).catch(() => setNotes([]));
    pmApi.notePages(pm.slug).then(setPages).catch(() => setPages([]));
  }
  useEffect(load, [pm?.slug]);

  async function create() {
    if (!form.trim()) return;
    try { await pmApi.createNote(pm.slug, { content: form }); setForm(""); load(); }
    catch (e) { setError(e.message || String(e)); }
  }

  if (!pmAuthed) return <SignInPrompt service="PM Again" children="Sign in to use notes." />;
  if (!pm) return <Empty title="PM Again is not linked" />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold">Notes</h1>
        <p className="text-sm text-gray-500">Quick notes + Notes Hub. Authority: PM Again.</p>
      </div>

      <Card className="px-4 py-3">
        <div className="flex gap-2">
          <input className="input flex-1" placeholder="Add a quick note…" value={form} onChange={(e) => setForm(e.target.value)} />
          <button onClick={create} disabled={!form.trim()} className="rounded-lg bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-700 disabled:opacity-50">Add Note</button>
        </div>
        {error && <div className="mt-2 text-xs text-rose-600">{error}</div>}
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader title={`Quick notes (${notes?.length ?? "…"})`} />
          {!notes ? <Loading /> : notes.length === 0 ? <Empty title="No notes" /> : (
            <ul className="divide-y divide-gray-100">
              {notes.map((n) => (
                <li key={n.id} className="px-4 py-2 text-sm text-gray-700">
                  {n.content}
                  <div className="text-[10px] text-gray-400">{n.status} · {formatDateTime(n.created_at)}</div>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card>
          <CardHeader title={`Notes Hub pages (${pages.length})`} />
          {pages.length === 0 ? <div className="px-4 py-3 text-sm text-gray-400">No note pages.</div> : (
            <ul className="divide-y divide-gray-100">
              {pages.map((p) => (
                <li key={p.id} className="px-4 py-2 text-sm">
                  <span className="font-medium text-gray-800">{p.title}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
