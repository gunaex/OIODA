import { useEffect, useState } from "react";
import { pmApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, StatusBadge, Loading, Empty, SignInPrompt, Table, Tr, Td } from "../components/ui";

export default function PmBoardPage() {
  const { pm, pmAuthed } = useProjectCtx();
  const [items, setItems] = useState(null);
  const [form, setForm] = useState({ item_type: "issue", title: "", severity: "P2", owner: "" });
  const [error, setError] = useState(null);

  function load() { if (pm?.slug) pmApi.boardItems(pm.slug).then(setItems).catch(() => setItems([])); }
  useEffect(load, [pm?.slug]);

  async function create() {
    if (!form.title.trim()) return;
    try {
      await pmApi.createBoardItem(pm.slug, { item_type: form.item_type, title: form.title, severity: form.severity || null, owner: form.owner || null });
      setForm({ item_type: "issue", title: "", severity: "P2", owner: "" });
      load();
    } catch (e) { setError(e.message || String(e)); }
  }

  async function promote(id) {
    try { await pmApi.promoteBoardItem(pm.slug, id); load(); }
    catch (e) { setError(e.message || String(e)); }
  }

  if (!pmAuthed) return <SignInPrompt service="PM Again" children="Sign in to use the board." />;
  if (!pm) return <Empty title="PM Again is not linked" />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold">Board</h1>
        <p className="text-sm text-gray-500">Issues, incidents and backlog. Authority: PM Again.</p>
      </div>

      <Card className="px-4 py-3">
        <div className="flex flex-wrap gap-2 text-sm">
          <select className="input !w-32" value={form.item_type} onChange={(e) => setForm({ ...form, item_type: e.target.value })}>
            {["issue", "incident", "backlog"].map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <input className="input flex-1" placeholder="Title *" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <input className="input !w-24" placeholder="Severity" value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })} />
          <input className="input !w-32" placeholder="Owner" value={form.owner} onChange={(e) => setForm({ ...form, owner: e.target.value })} />
          <button onClick={create} disabled={!form.title.trim()} className="rounded-lg bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-700 disabled:opacity-50">Add</button>
        </div>
        {error && <div className="mt-2 text-xs text-rose-600">{error}</div>}
      </Card>

      <Card>
        <CardHeader title={`Board items (${items?.length ?? "…"})`} />
        {!items ? <Loading /> : items.length === 0 ? <Empty title="No board items" /> : (
          <Table head={["Item", "Type", "Severity", "Status", "Owner", ""]}>
            {items.map((b) => (
              <Tr key={b.id}>
                <Td className="font-medium text-gray-800">{b.item_code ? `${b.item_code} — ` : ""}{b.title}</Td>
                <Td className="text-gray-500">{b.item_type}</Td>
                <Td className="text-gray-600">{b.severity || "—"}</Td>
                <Td><StatusBadge status={b.status} /></Td>
                <Td className="text-gray-600">{b.owner || "—"}</Td>
                <Td className="text-right">
                  {b.item_type !== "incident" && (
                    <button onClick={() => promote(b.id)} className="text-xs font-medium text-gray-900 hover:underline">Promote</button>
                  )}
                </Td>
              </Tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
