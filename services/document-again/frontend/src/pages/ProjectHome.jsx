import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import { useWorkspace } from "../App.jsx";
import { Card, StatusBadge, Empty, ErrorNote, Button } from "../components/ui.jsx";

/* External frontend origins (owner-facing cross-service links). */
const PM_ORIGIN = "http://localhost:5173";
const QA_ORIGIN = "http://localhost:5174";

const TYPE_TAG = {
  UR: "UR",
  DR: "DR",
  REQUIREMENT_REGISTER: "Register",
  TRACEABILITY_MATRIX: "Trace",
  ARCHITECTURE: "Architecture",
  PROCESS_FLOW: "Flow",
  CLARIFICATIONS_REGISTER: "Register",
  ASSUMPTIONS_REGISTER: "Register",
  DECISIONS_REGISTER: "Register",
};

/* Owner-facing trace relation labels (internal direction unchanged). */
function relationLabel(relation, objectType) {
  if (relation === "DERIVED_FROM") {
    if (objectType === "DOCUMENT_SECTION") return "Designed in";
    if (objectType === "PROCESS_STEP") return "Covered by flow step";
    if (objectType === "PROCESS_FLOW") return "Covered by flow";
    if (objectType === "ARCHITECTURE_NODE") return "Shown in architecture";
    return "Elaborated in";
  }
  if (relation === "REFERENCES") return "References";
  if (relation === "TRACES_TO") return "Traces to";
  return relation.replaceAll("_", " ").toLowerCase();
}

function DocRow({ doc }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);

  async function downloadExcel() {
    if (!doc.download) return;
    setBusy(true);
    try {
      const res = await fetch(doc.download, {
        headers: { "X-Actor": localStorage.getItem("da-actor") || "local-user" },
      });
      if (!res.ok) throw new Error("download failed");
      const blob = await res.blob();
      const cd = res.headers.get("content-disposition") || "";
      const m = cd.match(/filename="?([^"]+)"?/);
      const name = m ? m[1] : `${doc.title.replaceAll(" ", "_")}.xlsx`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = name; a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      // eslint-disable-next-line no-alert
      window.alert("Excel download failed: " + e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid grid-cols-[minmax(180px,2fr)_90px_55px_110px_125px_minmax(190px,1fr)] items-center gap-3 border-b border-line px-3 py-2.5 last:border-0">
      <span className="min-w-0 text-[13px] font-medium leading-5 text-slate-200" title={doc.title}>{doc.title}</span>
      <span className="rounded bg-surface-2 px-1.5 py-0.5 text-center text-[10px] font-semibold uppercase tracking-wide text-slate-400">
        {TYPE_TAG[doc.type] || doc.type}
      </span>
      <span className="text-[12px] text-slate-300">{doc.version ? `v${doc.version.replace("v", "")}` : "—"}</span>
      <span><StatusBadge status={doc.status} /></span>
      <span className="font-mono text-[11px] text-slate-500">
        {doc.updated_at ? doc.updated_at.slice(0, 16).replace("T", " ") : "—"}
      </span>
      <div className="flex items-center justify-end gap-1">
        <Button variant="primary" onClick={() => navigate(doc.open_route)}>Open</Button>
        {doc.download && (
          <Button variant="ghost" disabled={busy} onClick={downloadExcel}>Excel</Button>
        )}
        <Button variant="ghost" onClick={() => navigate("/baselines")}>History</Button>
      </div>
    </div>
  );
}

function RequirementRow({ req, onSelect, selected }) {
  const hasLinks = req.targets?.length > 0;
  return (
    <div className="border-b border-line last:border-0">
      <button
        onClick={() => onSelect(selected === req.code ? null : req.code)}
        className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-surface-2"
      >
        <span className="w-24 shrink-0 font-mono text-[12px] font-semibold text-brand-300">{req.code}</span>
        <span className="flex-1 text-[13px] text-slate-200">{req.title}</span>
        {hasLinks && <span className="text-[11px] text-slate-500">{req.targets.length} links</span>}
      </button>
      {selected === req.code && (
        <div className="space-y-1 bg-surface-2 px-3 py-2">
          {!hasLinks && <p className="text-[12px] text-slate-500">No linked design objects.</p>}
          {req.targets.map((t, i) => (
            <div key={i} className="flex items-center gap-2 text-[12px]">
              <span className="w-44 shrink-0 text-slate-500">{relationLabel(t.relation, t.object_type)}</span>
              <span className="text-slate-200">{t.display_name}</span>
              {t.object_type && <span className="text-[10px] uppercase text-slate-600">{t.object_type.replaceAll("_", " ")}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function ProjectHome() {
  const { project } = useWorkspace();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [selReq, setSelReq] = useState(null);

  useEffect(() => {
    if (!project) return;
    setData(null); setSelReq(null);
    api.get(`/projects/${project.id}/home`).then(setData).catch(setError);
  }, [project?.id]);

  if (error) return <ErrorNote error={error} />;
  if (!data) return <p className="p-6 text-[13px] text-slate-500">Loading project home…</p>;

  return (
    <div className="space-y-4">
      {/* ── Project identity header ── */}
      <div className="rounded-lg border border-brand-500/30 bg-surface-1 p-5 shadow-sm">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h1 className="text-[22px] font-bold tracking-tight text-slate-100">{data.project.name}</h1>
          <span className="rounded bg-surface-2 px-1.5 py-0.5 text-[11px] text-slate-400">{data.project.key}</span>
        </div>
        <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-[12px] text-slate-400">
          <span>Current baseline: <b className="text-slate-200">{data.current_baseline?.name || "—"}</b></span>
          <span>Last updated: <b className="text-slate-200">{data.last_updated?.slice(0, 16).replace("T", " ")}</b></span>
          <span>Open clarifications: <b className="text-amber-300">{data.open_clarifications}</b></span>
          <span>Requirements: <b className="text-slate-200">{data.requirements.length}</b></span>
        </div>
      </div>

      {/* ── PM / QA status continuity ── */}
      <div className="grid gap-3 xl:grid-cols-2">
        <Card title="Execution — PM Again">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[13px] text-slate-200">Work status: <b>{data.pm.work_status || "Open in PM for current status"}</b></p>
              <p className="mt-1 text-[11px] text-slate-500">
                {data.pm.handoff ? `Document delivery: ${data.pm.human} · ${data.current_baseline?.name || "No baseline"}` : "Documents have not been sent"}
              </p>
            </div>
            <a href={PM_ORIGIN} target="_blank" rel="noreferrer">
              <Button variant="default">Open PM</Button>
            </a>
          </div>
        </Card>
        <Card title="Verification — QA Again">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[13px] text-slate-200">Validation status: <b>{data.qa.work_status || "Open QA for current status"}</b></p>
              <p className="mt-1 text-[11px] text-slate-500">
                {data.qa.handoff ? `Document delivery: ${data.qa.human} · ${data.current_baseline?.name || "No baseline"}` : "Documents have not been sent"}
              </p>
            </div>
            <a href={QA_ORIGIN} target="_blank" rel="noreferrer">
              <Button variant="default">Open QA</Button>
            </a>
          </div>
        </Card>
      </div>

      {/* ── Project documents ── */}
      <Card title="Project documents">
        {data.documents.length === 0 && <Empty>No documents yet.</Empty>}
        {data.documents.length > 0 && (
          <div className="overflow-x-auto">
            <div className="min-w-[880px]">
              <div className="grid grid-cols-[minmax(180px,2fr)_90px_55px_110px_125px_minmax(190px,1fr)] gap-3 border-b border-line px-3 pb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                <span>Title</span><span>Type</span><span>Version</span><span>Status</span><span>Updated</span><span className="text-right">Actions</span>
              </div>
              {data.documents.map((d) => <DocRow key={d.key + d.type} doc={d} />)}
            </div>
          </div>
        )}
      </Card>

      {/* ── Requirements & human-readable trace ── */}
      <Card title="Requirements & trace — click a requirement to see linked design">
        {data.requirements.map((r) => (
          <RequirementRow key={r.code} req={r} selected={selReq} onSelect={setSelReq} />
        ))}
      </Card>

      {/* ── Latest activity ── */}
      <Card title="Latest activity">
        {data.activity.length === 0 && <Empty>No activity yet.</Empty>}
        <ol className="space-y-1">
          {data.activity.slice(0, 12).map((ev, i) => (
            <li key={i} className="flex items-center gap-3 text-[12px]">
              <span className="w-32 shrink-0 font-mono text-[11px] text-slate-500">
                {ev.at.slice(0, 16).replace("T", " ")}
              </span>
              <span className="text-slate-200">{ev.label}</span>
              {ev.actor && <span className="text-slate-600">· {ev.actor}</span>}
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}
