import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { documentApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, Table, Tr, Td, Badge, StatusBadge, Loading, Empty } from "../components/ui";

export default function Requirements() {
  const { project } = useProjectCtx();
  const [requirements, setRequirements] = useState(null);
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", priority: "", source_type: "CUSTOMER", source_reference: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  function load() {
    if (project) documentApi.listRequirements(project.id).then(setRequirements).catch(() => setRequirements([]));
  }
  useEffect(load, [project?.id]);

  async function create() {
    if (!form.title.trim()) return;
    setBusy(true); setError(null);
    try {
      await documentApi.createRequirement({
        project_id: project.id,
        title: form.title,
        description: form.description || null,
        priority: form.priority || null,
        source_type: form.source_type || null,
        source_reference: form.source_reference || null,
      });
      setShowNew(false);
      setForm({ title: "", description: "", priority: "", source_type: "CUSTOMER", source_reference: "" });
      load();
    } catch (e) { setError(e.message || String(e)); }
    finally { setBusy(false); }
  }

  if (!project) return <Loading />;

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-lg font-bold">Requirement Register</h1>
          <p className="text-sm text-gray-500">
            {requirements?.length ?? "…"} requirements · Source: Document Again
          </p>
        </div>
        <button onClick={() => setShowNew((v) => !v)} className="rounded-lg bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-700">
          + New Requirement
        </button>
      </div>

      {showNew && (
        <Card className="px-4 py-3">
          <div className="grid gap-2 text-sm">
            <input className="input" placeholder="Requirement title *" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            <textarea className="input min-h-16" placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            <div className="grid grid-cols-3 gap-2">
              <input className="input" placeholder="Priority (e.g. High)" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })} />
              <select className="input" value={form.source_type} onChange={(e) => setForm({ ...form, source_type: e.target.value })}>
                {["CUSTOMER", "REGULATORY", "ARCHITECT", "INTERNAL", "OTHER"].map((s) => <option key={s}>{s}</option>)}
              </select>
              <input className="input" placeholder="Source reference" value={form.source_reference} onChange={(e) => setForm({ ...form, source_reference: e.target.value })} />
            </div>
            <div className="flex items-center gap-2">
              <button onClick={create} disabled={busy || !form.title.trim()} className="rounded-lg bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-700 disabled:opacity-50">Create Requirement</button>
              <span className="text-[11px] text-gray-400">Saved to Document Again — the requirement authority. A code is auto-assigned.</span>
            </div>
            {error && <span className="text-xs text-rose-600">{error}</span>}
          </div>
        </Card>
      )}

      <Card>
        <CardHeader title="Requirements" subtitle="Click a requirement to see its full trace." />
        {!requirements ? (
          <Loading />
        ) : requirements.length === 0 ? (
          <Empty title="No requirements" />
        ) : (
          <Table head={["Code", "Title", "Status", "Source", ""]}>
            {requirements.map((r) => (
              <Tr key={r.id}>
                <Td>
                  <Link to={`/projects/${project.id}/requirements/${r.code}`} className="font-semibold text-gray-900 hover:underline">
                    {r.code}
                  </Link>
                </Td>
                <Td className="text-gray-700">{r.title}</Td>
                <Td><StatusBadge status={r.status} /></Td>
                <Td className="text-gray-500">{r.source_type || "—"}</Td>
                <Td className="text-right">
                  <Link to={`/projects/${project.id}/requirements/${r.code}`} className="text-sm font-medium text-gray-900 hover:underline">
                    Trace →
                  </Link>
                </Td>
              </Tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
