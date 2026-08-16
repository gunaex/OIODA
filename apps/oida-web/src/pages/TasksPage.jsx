import { useEffect, useState } from "react";
import { pmApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, StatusBadge, Loading, Empty, SignInPrompt, Table, Tr, Td, formatDate } from "../components/ui";

const STATUSES = ["Todo", "InProgress", "Done", "Blocked"];
const PRIORITIES = ["Low", "Med", "High"];

export default function TasksPage() {
  const { pm, pmAuthed } = useProjectCtx();
  const [tasks, setTasks] = useState(null);
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState({ title: "", owner: "", status: "Todo", priority: "Med", due_date: "", linked_function_id: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  function load() {
    if (pm?.slug) pmApi.tasks(pm.slug).then(setTasks).catch(() => setTasks([]));
  }
  useEffect(load, [pm?.slug]);

  async function create() {
    if (!form.title.trim()) return;
    setBusy(true); setError(null);
    try {
      await pmApi.createTask(pm.slug, {
        title: form.title, owner: form.owner || null, status: form.status, priority: form.priority,
        due_date: form.due_date || null, linked_function_id: form.linked_function_id ? Number(form.linked_function_id) : null,
      });
      setShowNew(false);
      setForm({ title: "", owner: "", status: "Todo", priority: "Med", due_date: "", linked_function_id: "" });
      load();
    } catch (e) { setError(e.message || String(e)); }
    finally { setBusy(false); }
  }

  async function setStatus(t, status) {
    setBusy(true); setError(null);
    try { await pmApi.updateTask(pm.slug, t.id, { title: t.title, status }); load(); }
    catch (e) { setError(e.message || String(e)); }
    finally { setBusy(false); }
  }

  async function setOwner(t, owner) {
    setBusy(true); setError(null);
    try { await pmApi.updateTask(pm.slug, t.id, { title: t.title, owner: owner || null }); load(); }
    catch (e) { setError(e.message || String(e)); }
    finally { setBusy(false); }
  }

  if (!pmAuthed) return <SignInPrompt service="PM Again" children="Sign in to manage the requirement-backed tasks." />;
  if (!pm) return <Empty title="PM Again is not linked" />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold">Tasks</h1>
          <p className="text-sm text-gray-500">Task authority: PM Again. Edits go straight to PM Again — OIDA keeps no copy.</p>
        </div>
        <button onClick={() => setShowNew((v) => !v)} className="rounded-lg bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-700">
          + New Task
        </button>
      </div>

      {showNew && (
        <Card className="px-4 py-3">
          <div className="grid gap-2 text-sm md:grid-cols-3">
            <input className="input" placeholder="Task title *" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            <input className="input" placeholder="Owner" value={form.owner} onChange={(e) => setForm({ ...form, owner: e.target.value })} />
            <input className="input" placeholder="Linked function id (optional)" value={form.linked_function_id} onChange={(e) => setForm({ ...form, linked_function_id: e.target.value })} />
            <select className="input" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
              {STATUSES.map((s) => <option key={s}>{s}</option>)}
            </select>
            <select className="input" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
              {PRIORITIES.map((s) => <option key={s}>{s}</option>)}
            </select>
            <input type="date" className="input" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
          </div>
          <div className="mt-2 flex items-center gap-2">
            <button onClick={create} disabled={busy || !form.title.trim()} className="rounded-lg bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-700 disabled:opacity-50">Create Task</button>
            {error && <span className="text-xs text-rose-600">{error}</span>}
          </div>
        </Card>
      )}

      <Card>
        <CardHeader title={`Tasks (${tasks?.length ?? "…"})`} subtitle="Click a status to transition it." />
        {!tasks ? (
          <Loading />
        ) : tasks.length === 0 ? (
          <Empty title="No tasks" />
        ) : (
          <Table head={["Task", "Workstream", "Status", "Owner", "Priority", "Due"]}>
            {tasks.map((t) => (
              <Tr key={t.id}>
                <Td className="font-medium text-gray-800">{t.title}</Td>
                <Td className="text-gray-500">{t.linked_function_id ? `#${t.linked_function_id}` : "—"}</Td>
                <Td>
                  <div className="flex flex-wrap gap-1">
                    {STATUSES.map((s) => (
                      <button key={s} onClick={() => setStatus(t, s)} className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${t.status === s ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}>{s}</button>
                    ))}
                  </div>
                </Td>
                <Td>
                  <input
                    className="w-28 rounded border border-gray-200 px-1.5 py-0.5 text-xs"
                    defaultValue={t.owner || ""}
                    placeholder="Unassigned"
                    onBlur={(e) => { if (e.target.value !== (t.owner || "")) setOwner(t, e.target.value); }}
                  />
                </Td>
                <Td className="text-gray-600">{t.priority || "—"}</Td>
                <Td className="text-gray-600">{t.due_date ? formatDate(t.due_date) : "Not Scheduled"}</Td>
              </Tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
