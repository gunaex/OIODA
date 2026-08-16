import { useEffect, useState } from "react";
import { qaApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, StatusBadge, Loading, Empty, SignInPrompt, Table, Tr, Td } from "../components/ui";

export default function QaDefectsPage() {
  const { qa, qaAuthed } = useProjectCtx();
  const slug = qa && qa.length ? qa[0].slug : null;
  const [defects, setDefects] = useState(null);
  const [form, setForm] = useState({ title: "", severity: "UNSPECIFIED", description_md: "" });
  const [error, setError] = useState(null);

  function load() { if (slug) qaApi.defects(slug).then(setDefects).catch(() => setDefects([])); }
  useEffect(load, [slug]);

  async function create() {
    if (!form.title.trim()) return;
    try { await qaApi.createDefect(slug, { title: form.title, severity: form.severity, description_md: form.description_md || null }); setForm({ title: "", severity: "UNSPECIFIED", description_md: "" }); load(); }
    catch (e) { setError(e.message || String(e)); }
  }

  if (!qaAuthed) return <SignInPrompt service="QA Again" children="Sign in to manage defects." />;
  if (!slug) return <Empty title="QA Again is not linked" />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold">Defects</h1>
        <p className="text-sm text-gray-500">Defect authority: QA Again.</p>
      </div>

      <Card className="px-4 py-3">
        <div className="flex flex-wrap gap-2 text-sm">
          <input className="input flex-1" placeholder="Defect title *" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <select className="input !w-36" value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })}>
            {["P0", "P1", "P2", "P3", "UNSPECIFIED"].map((s) => <option key={s}>{s}</option>)}
          </select>
          <button onClick={create} disabled={!form.title.trim()} className="rounded-lg bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-700 disabled:opacity-50">Raise Defect</button>
        </div>
        {error && <div className="mt-2 text-xs text-rose-600">{error}</div>}
      </Card>

      <Card>
        <CardHeader title={`Defects (${defects?.length ?? "…"})`} />
        {!defects ? <Loading /> : defects.length === 0 ? <Empty title="No defects" /> : (
          <Table head={["Defect", "Severity", "Status", "Description"]}>
            {defects.map((d) => (
              <Tr key={d.id}>
                <Td className="font-medium text-gray-800">{d.defect_key ? `${d.defect_key} — ` : ""}{d.title}</Td>
                <Td className="text-gray-600">{d.severity}</Td>
                <Td><StatusBadge status={d.status} /></Td>
                <Td className="text-gray-500">{d.description_md || "—"}</Td>
              </Tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
