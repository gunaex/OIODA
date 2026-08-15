import React, { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useWorkspace } from "../App.jsx";
import { Card, Empty, ErrorNote } from "../components/ui.jsx";

const EVENT_LABELS = {
  DESIGN_BASELINED: "Design baselined",
  REQUIREMENT_BASELINED: "Requirement baselined",
  CHANGE_REQUEST_APPROVED: "Change request approved",
  DESIGN_CHANGED: "Design changed",
  EXECUTION_REQUESTED: "Execution requested (PM)",
  QA_VALIDATION_REQUESTED: "Validation requested (QA)",
  QA_RESULT_RECEIVED: "QA result received",
  RELEASE_LINKED: "Release linked",
};

function StatusBadge({ status }) {
  const color = {
    PENDING: "bg-amber-500/20 text-amber-200",
    SENT: "bg-sky-500/20 text-sky-200",
    ACKNOWLEDGED: "bg-emerald-500/20 text-emerald-200",
    FAILED: "bg-red-500/20 text-red-200",
    DRAFT: "bg-slate-500/20 text-slate-300",
    READY: "bg-sky-500/20 text-sky-200",
    CANCELLED: "bg-slate-500/20 text-slate-400",
  }[status] || "bg-slate-500/20 text-slate-300";
  return <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${color}`}>{status}</span>;
}

export function Ecosystem() {
  const { project } = useWorkspace();
  const [events, setEvents] = useState([]);
  const [outbox, setOutbox] = useState([]);
  const [pm, setPm] = useState([]);
  const [qa, setQa] = useState([]);
  const [refs, setRefs] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!project) return;
    Promise.all([
      api.get(`/projects/${project.id}/ecosystem-events`),
      api.get("/outbox"),
      api.get(`/projects/${project.id}/handoffs/execution`),
      api.get(`/projects/${project.id}/handoffs/qa`),
      api.get(`/projects/${project.id}/external-references`),
    ]).then(([ev, ob, p, q, r]) => {
      setEvents(ev); setOutbox(ob); setPm(p); setQa(q); setRefs(r);
    }).catch(setError);
  }, [project?.id]);

  const counts = outbox.reduce((acc, o) => {
    acc[o.status] = (acc[o.status] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      <ErrorNote error={error} />

      <Card title="Ecosystem status — durable integration outbox">
        <div className="flex gap-3">
          {["PENDING", "SENT", "ACKNOWLEDGED", "FAILED"].map((s) => (
            <div key={s} className="flex-1 rounded border border-line bg-surface-2 p-3 text-center">
              <p className="text-[22px] font-bold text-slate-200">{counts[s] || 0}</p>
              <p className="text-[11px] uppercase tracking-wider text-slate-500">{s.toLowerCase()}</p>
            </div>
          ))}
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3 text-[12px] text-slate-400">
          <p>PM handoffs: <b className="text-slate-200">{pm.length}</b> · QA handoffs: <b className="text-slate-200">{qa.length}</b></p>
          <p>External references: <b className="text-slate-200">{refs.length}</b></p>
        </div>
      </Card>

      <Card title="Handoffs (PM / QA)">
        {pm.length === 0 && qa.length === 0 && <Empty>No handoffs yet. Confirm a baseline, then hand it off to PM or QA.</Empty>}
        {pm.map((h) => (
          <div key={h.id} className="mb-2 flex items-center gap-3 rounded border border-line bg-surface-2 p-2 text-[12px]">
            <span className="rounded bg-brand-600/20 px-1.5 py-0.5 font-bold text-brand-100">PM</span>
            <span className="font-mono text-slate-300">{h.id}</span>
            <span className="text-slate-500">→ {h.target_service}</span>
            <StatusBadge status={h.status} />
            {h.external_reference && <span className="text-slate-400">ref: {h.external_reference}</span>}
          </div>
        ))}
        {qa.map((h) => (
          <div key={h.id} className="mb-2 flex items-center gap-3 rounded border border-line bg-surface-2 p-2 text-[12px]">
            <span className="rounded bg-emerald-600/20 px-1.5 py-0.5 font-bold text-emerald-100">QA</span>
            <span className="font-mono text-slate-300">{h.id}</span>
            <span className="text-slate-500">→ {h.target_service}</span>
            <StatusBadge status={h.status} />
            {h.target_release && <span className="text-slate-400">release: {h.target_release}</span>}
          </div>
        ))}
      </Card>

      <Card title="Activity timeline — ecosystem events">
        {events.length === 0 && <Empty>No ecosystem events emitted yet.</Empty>}
        <ol className="space-y-2">
          {events.map((ev) => (
            <li key={ev.id} className="flex items-start gap-3 rounded border border-line bg-surface-2 p-2 text-[12px]">
              <span className="w-32 shrink-0 font-mono text-[11px] text-slate-500">
                {ev.occurred_at.slice(0, 19).replace("T", " ")}
              </span>
              <span className="w-44 shrink-0 font-semibold text-slate-200">
                {EVENT_LABELS[ev.event_type] || ev.event_type}
              </span>
              <span className="shrink-0 text-slate-500">{ev.source_service}</span>
              <span className="truncate font-mono text-slate-400">{ev.correlation_id}</span>
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}
