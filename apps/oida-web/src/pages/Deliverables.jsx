import { useEffect, useMemo, useState } from "react";
import { deliverableApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import {
  Card, CardHeader, StatCard, Table, Tr, Td, Badge, Loading, OidaError,
} from "../components/ui";
import { Download, RefreshCw, AlertTriangle } from "lucide-react";

const APPL_TONE = {
  MANDATORY: "rose",
  RECOMMENDED: "amber",
  CONDITIONAL: "gray",
  OPTIONAL: "gray",
  NOT_APPLICABLE: "gray",
};
const LIFE_TONE = {
  MISSING: "rose",
  DRAFT: "amber",
  INTERNAL_REVIEW: "blue",
  CUSTOMER_REVIEW: "blue",
  APPROVED: "green",
  BASELINED: "emerald",
  SUPERSEDED: "gray",
  ARCHIVED: "gray",
  "N/A": "gray",
};

const WORKBOOKS = ["PROJECT_MASTER", "INFRA_DESIGN", "MIGRATION_PLAN", "SECURITY_REGISTER", "APPLICATION_DESIGN"];

export default function Deliverables() {
  const { project } = useProjectCtx();
  const [taxonomy, setTaxonomy] = useState(null);
  const [profile, setProfile] = useState(null);
  const [matrix, setMatrix] = useState(null);
  const [gaps, setGaps] = useState(null);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState("All");
  const [selected, setSelected] = useState(null);
  const [busy, setBusy] = useState(false);

  function load() {
    if (!project) return;
    deliverableApi.taxonomy().then(setTaxonomy).catch(() => {});
    deliverableApi.profile(project.id).then(setProfile).catch(() => {});
    deliverableApi.matrix(project.id).then(setMatrix).catch((e) => setError(e.message));
    deliverableApi.gaps(project.id).then(setGaps).catch(() => {});
  }
  useEffect(load, [project?.id]);

  async function saveProfile() {
    if (!profile) return;
    setBusy(true); setError(null);
    try {
      const next = await deliverableApi.putProfile(project.id, {
        primary_type: profile.primary_type,
        workstreams: profile.workstreams,
        attributes: profile.attributes,
        confirmed: true,
      });
      setProfile(next);
      const m = await deliverableApi.generateMatrix(project.id);
      setMatrix(m);
      deliverableApi.gaps(project.id).then(setGaps).catch(() => {});
    } catch (e) { setError(e.message || String(e)); }
    finally { setBusy(false); }
  }

  async function regenerate() {
    setBusy(true); setError(null);
    try {
      const m = await deliverableApi.generateMatrix(project.id);
      setMatrix(m);
      deliverableApi.gaps(project.id).then(setGaps).catch(() => {});
    } catch (e) { setError(e.message || String(e)); }
    finally { setBusy(false); }
  }

  async function download(mode) {
    const base = (import.meta.env.VITE_API_BASE || "").replace(/\/+$/, "");
    const url = `${base}/api/da/projects/${project.id}/exports/${mode}`;
    const token = localStorage.getItem("oida_ecosystem_token");
    const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${project.key}-${mode}.xlsx`;
    a.click();
  }

  const rows = useMemo(() => {
    if (!matrix) return [];
    if (filter === "All") return matrix.rows;
    if (filter === "N/A") return matrix.rows.filter((r) => r.applicability === "NOT_APPLICABLE");
    if (filter === "Missing") return matrix.rows.filter((r) => r.lifecycle_status === "MISSING");
    if (filter === "Draft") return matrix.rows.filter((r) => r.lifecycle_status === "DRAFT");
    if (filter === "Review") return matrix.rows.filter((r) => ["INTERNAL_REVIEW", "CUSTOMER_REVIEW"].includes(r.lifecycle_status));
    if (filter === "Approved") return matrix.rows.filter((r) => ["APPROVED", "BASELINED"].includes(r.lifecycle_status));
    return matrix.rows.filter((r) => r.applicability === filter);
  }, [matrix, filter]);

  if (!project) return <Loading />;
  if (error && !matrix) return <OidaError message={String(error)} onRetry={load} />;

  const s = matrix?.summary;

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold">Project Deliverables</h1>
          <p className="text-sm text-gray-500">Universal deliverable standard framework — applicability is rule-derived and explainable.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={regenerate} disabled={busy}
            className="inline-flex items-center gap-1 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm hover:bg-gray-50 disabled:opacity-50">
            <RefreshCw size={14} /> Re-evaluate
          </button>
        </div>
      </div>

      {s && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
          <StatCard label="Mandatory" value={s.by_applicability?.MANDATORY ?? 0} tone="rose" />
          <StatCard label="Recommended" value={s.by_applicability?.RECOMMENDED ?? 0} tone="amber" />
          <StatCard label="N/A" value={s.by_applicability?.NOT_APPLICABLE ?? 0} tone="gray" />
          <StatCard label="Missing" value={s.missing ?? 0} tone="rose" />
          <StatCard label="Draft / Review" value={s.draft_review ?? 0} tone="blue" />
          <StatCard label="Approved / Baselined" value={s.approved_baselined ?? 0} tone="emerald" />
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader title="Project Profile" subtitle="Primary type + workstreams + attributes drive applicability." />
          {profile && taxonomy && (
            <div className="space-y-4 p-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-600">Primary Project Type</label>
                <select value={profile.primary_type || ""} onChange={(e) => setProfile({ ...profile, primary_type: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-2 py-2 text-sm">
                  <option value="">— not set —</option>
                  {taxonomy.project_types.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-600">Workstreams</label>
                <div className="grid max-h-56 grid-cols-1 gap-1 overflow-auto rounded-lg border border-gray-200 p-2">
                  {taxonomy.workstreams.map((w) => (
                    <label key={w} className="flex items-center gap-2 text-xs">
                      <input type="checkbox" checked={(profile.workstreams || []).includes(w)}
                        onChange={(e) => {
                          const ws = new Set(profile.workstreams || []);
                          if (e.target.checked) ws.add(w); else ws.delete(w);
                          setProfile({ ...profile, workstreams: [...ws] });
                        }} />
                      {w}
                    </label>
                  ))}
                </div>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-600">Attributes</label>
                <div className="grid grid-cols-1 gap-1">
                  {Object.entries(profile.attributes || {}).map(([k, v]) => (
                    <label key={k} className="flex items-center gap-2 text-xs">
                      <input type="checkbox" checked={!!v} onChange={(e) => setProfile({ ...profile, attributes: { ...profile.attributes, [k]: e.target.checked } })} />
                      {k}
                    </label>
                  ))}
                </div>
              </div>
              <button onClick={saveProfile} disabled={busy}
                className="w-full rounded-lg bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50">
                {busy ? "Saving…" : "Save & Apply Classification"}
              </button>
            </div>
          )}
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Deliverable Matrix" subtitle={matrix ? `${matrix.rows.length} standards` : ""}
            right={
              <div className="flex flex-wrap gap-1">
                {["All", "Mandatory", "Missing", "Draft", "Review", "Approved", "N/A"].map((f) => (
                  <button key={f} onClick={() => setFilter(f)}
                    className={`rounded px-2 py-1 text-xs ${filter === f ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}>
                    {f}
                  </button>
                ))}
              </div>
            } />
          {rows && (
            <Table head={["Deliverable", "Domain", "Applicability", "Status", "Owner", "Version"]}>
              {rows.slice(0, 400).map((r) => (
                <Tr key={r.code} onClick={() => setSelected(r)} className="cursor-pointer hover:bg-gray-50">
                  <Td><div className="font-medium">{r.name}</div><div className="text-xs text-gray-400">{r.document_id || r.code}</div></Td>
                  <Td>{r.domain}</Td>
                  <Td><Badge tone={APPL_TONE[r.applicability] || "gray"}>{r.applicability}</Badge></Td>
                  <Td><Badge tone={LIFE_TONE[r.lifecycle_status] || "gray"}>{r.lifecycle_status}</Badge></Td>
                  <Td>{r.owner || "—"}</Td>
                  <Td>{r.version || "—"}</Td>
                </Tr>
              ))}
            </Table>
          )}
        </Card>
      </div>

      {gaps && gaps.summary.mandatory_missing > 0 && (
        <Card>
          <CardHeader title="Gap Detection" subtitle={`${gaps.summary.mandatory_missing} mandatory deliverables missing`}
            right={<AlertTriangle size={16} className="text-rose-500" />} />
          <div className="grid grid-cols-2 gap-2 p-4 md:grid-cols-3">
            {gaps.gaps.mandatory_missing.slice(0, 30).map((g) => (
              <div key={g.code} className="rounded-lg border border-rose-100 bg-rose-50 px-3 py-2 text-xs">
                <span className="font-medium text-rose-700">{g.name}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card>
        <CardHeader title="Export" subtitle="Standard workbooks — XLSX first class." />
        <div className="flex flex-wrap gap-2 p-4">
          {WORKBOOKS.map((m) => (
            <button key={m} onClick={() => download(m)}
              className="inline-flex items-center gap-1 rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs hover:bg-gray-50">
              <Download size={13} /> {m}.xlsx
            </button>
          ))}
        </div>
      </Card>

      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setSelected(null)}>
          <div className="max-h-[85vh] w-full max-w-2xl overflow-auto rounded-xl bg-white p-6" onClick={(e) => e.stopPropagation()}>
            <div className="mb-4 flex items-start justify-between">
              <div>
                <h2 className="text-lg font-bold">{selected.name}</h2>
                <div className="mt-1 flex flex-wrap gap-2 text-xs text-gray-500">
                  <span>{selected.document_id || selected.code}</span>
                  <span>·</span><span>{selected.domain} / {selected.category}</span>
                  <span>·</span><span>template {selected.template_version}</span>
                </div>
              </div>
              <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-gray-700">✕</button>
            </div>
            <div className="mb-4 flex gap-2">
              <Badge tone={APPL_TONE[selected.applicability] || "gray"}>{selected.applicability}</Badge>
              <Badge tone={LIFE_TONE[selected.lifecycle_status] || "gray"}>{selected.lifecycle_status}</Badge>
            </div>
            <div className="mb-4 rounded-lg bg-gray-50 p-3">
              <div className="text-xs font-semibold text-gray-500">Why applicable?</div>
              <ul className="mt-1 list-disc pl-5 text-sm text-gray-700">
                {(selected.reason || []).map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            </div>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <dt className="text-gray-500">Owner</dt><dd>{selected.owner || "—"}</dd>
              <dt className="text-gray-500">Version</dt><dd>{selected.version || "—"}</dd>
              <dt className="text-gray-500">Layout Template</dt><dd>{selected.layout_template}</dd>
              <dt className="text-gray-500">Source Authorities</dt><dd>{(selected.source_authorities || []).join(", ") || "—"}</dd>
            </dl>
          </div>
        </div>
      )}
    </div>
  );
}
