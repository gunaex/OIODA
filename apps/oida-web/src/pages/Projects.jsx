import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { documentApi } from "../api";
import { Card, Loading, OidaError, Badge, formatDateTime } from "../components/ui";
import { Boxes, Archive, RotateCcw, Copy, Trash2 } from "lucide-react";
import NewProjectModal from "../components/NewProjectModal";

const STATE_TONE = { ACTIVE: "green", ARCHIVED: "amber", DELETE_REQUESTED: "red", DELETED: "gray" };

function CloneModal({ project, onClose, onDone }) {
  const [name, setName] = useState(`${project.name} - Clone`);
  const [key, setKey] = useState(`${project.key}C`);
  const [busy, setBusy] = useState(false);
  async function submit() {
    setBusy(true);
    try {
      const res = await documentApi.cloneProject(project.id, { key, name });
      onDone(res);
    } finally { setBusy(false); }
  }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <Card className="w-full max-w-md px-5 py-4">
        <h3 className="text-sm font-semibold text-gray-800">Clone Project</h3>
        <p className="mt-1 text-xs text-gray-500">Creates a new project using reusable knowledge (requirements, architecture, planning, QA design). Execution / CR / Council history is NOT cloned.</p>
        <div className="mt-3 grid gap-2 text-sm">
          <input className="input" placeholder="New project name" value={name} onChange={(e) => setName(e.target.value)} />
          <input className="input" placeholder="New project key" value={key} onChange={(e) => setKey(e.target.value)} />
          <div className="text-[11px] text-gray-400">
            Include by default: Requirements · Architecture · PM planning · QA test design.<br />
            Never cloned: PM execution history · QA results · Defects · CR history · Council history.
          </div>
        </div>
        <div className="mt-3 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50">Cancel</button>
          <button onClick={submit} disabled={busy || !name.trim() || !key.trim()} className="rounded-lg bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-700 disabled:opacity-50">Clone</button>
        </div>
      </Card>
    </div>
  );
}

function DeleteModal({ project, onClose, onDone }) {
  const [impact, setImpact] = useState(null);
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { documentApi.deleteImpact(project.id).then(setImpact).catch(() => setImpact(null)); }, [project.id]);
  const counts = impact?.document || {};
  async function submit() {
    setBusy(true);
    try {
      const res = await documentApi.deleteProject(project.id, confirm);
      onDone(res);
    } finally { setBusy(false); }
  }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <Card className="w-full max-w-md px-5 py-4">
        <h3 className="text-sm font-semibold text-rose-700">Delete {project.name}?</h3>
        <div className="mt-2 grid grid-cols-2 gap-1 text-xs text-gray-600">
          {Object.entries(counts).map(([k, v]) => (
            <span key={k}>{k.replaceAll("_", " ")}: <b>{v}</b></span>
          ))}
        </div>
        <p className="mt-2 text-[11px] text-gray-500">Bounded services (PM/QA/Infra) report their own delete capability. Document truth is tombstoned (retained for audit).</p>
        <div className="mt-3 text-sm">
          <div className="text-xs text-gray-500">Type project key to confirm: <b>{project.key}</b></div>
          <input className="input mt-1 w-full" value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder={project.key} />
        </div>
        <div className="mt-3 flex justify-end gap-2">
          <button onClick={onClose} className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50">Cancel</button>
          <button onClick={submit} disabled={busy || confirm.trim().toUpperCase() !== (project.key || "").toUpperCase()} className="rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-rose-700 disabled:opacity-50">Delete</button>
        </div>
      </Card>
    </div>
  );
}

export default function Projects() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState(null);
  const [error, setError] = useState(null);
  const [showNew, setShowNew] = useState(false);
  const [tab, setTab] = useState("ACTIVE");
  const [cloneTarget, setCloneTarget] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [msg, setMsg] = useState(null);

  async function load() {
    setError(null);
    try {
      setProjects(await documentApi.listProjects(tab === "ALL" ? null : tab));
    } catch (err) {
      setError(err);
    }
  }

  useEffect(() => { load(); }, [tab]);

  async function action(fn, doneMsg) {
    setError(null); setMsg(null);
    try {
      await fn();
      setMsg(doneMsg);
      load();
    } catch (err) { setError(err); }
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Boxes size={24} className="text-gray-900" />
          <div>
            <h1 className="text-xl font-bold tracking-tight">Projects</h1>
            <p className="text-sm text-gray-500">One product. Multiple bounded services behind it.</p>
          </div>
        </div>
        <button onClick={() => setShowNew(true)} className="rounded-lg bg-gray-900 px-3.5 py-2 text-sm font-medium text-white hover:bg-gray-700">
          + New Project
        </button>
      </div>

      <div className="mb-4 flex gap-1.5">
        {["ACTIVE", "ARCHIVED", "ALL"].map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`rounded-lg px-3 py-1.5 text-xs font-medium ${tab === t ? "bg-gray-900 text-white" : "border border-gray-200 text-gray-600 hover:bg-gray-50"}`}>
            {t === "ALL" ? "All" : t.charAt(0) + t.slice(1).toLowerCase()}
          </button>
        ))}
      </div>

      {msg && <div className="mb-3 text-xs text-emerald-600">{msg}</div>}
      {error && <OidaError message={String(error.message || error)} onRetry={load} />}
      {!error && !projects && <Loading />}

      {projects && (
        <div className="space-y-3">
          {projects.map((p) => (
            <Card key={p.id} className="flex items-center justify-between gap-3 px-5 py-4">
              <Link to={p.lifecycle_state === "DELETED" ? "#" : `/projects/${p.id}`} className="min-w-0 flex-1">
                <div className="text-base font-semibold text-gray-900">{p.name}</div>
                <div className="mt-0.5 text-xs text-gray-500">
                  {p.description || "No description"} · {formatDateTime(p.created_at)}
                  {p.cloned_from_project_id && <span className="ml-2 text-violet-500">cloned</span>}
                </div>
              </Link>
              <div className="flex items-center gap-1.5">
                {p.key && <Badge tone="violet">{p.key}</Badge>}
                <Badge tone={STATE_TONE[p.lifecycle_state] || "gray"}>{p.lifecycle_state}</Badge>
                {p.lifecycle_state === "ACTIVE" && (
                  <button title="Archive" onClick={() => action(() => documentApi.archiveProject(p.id), `${p.name} archived.`)} className="rounded border border-gray-200 p-1.5 text-gray-500 hover:bg-gray-50"><Archive size={14} /></button>
                )}
                {p.lifecycle_state === "ARCHIVED" && (
                  <>
                    <button title="Restore" onClick={() => action(() => documentApi.restoreProject(p.id), `${p.name} restored.`)} className="rounded border border-gray-200 p-1.5 text-gray-500 hover:bg-gray-50"><RotateCcw size={14} /></button>
                    <button title="Delete" onClick={() => setDeleteTarget(p)} className="rounded border border-gray-200 p-1.5 text-rose-500 hover:bg-rose-50"><Trash2 size={14} /></button>
                  </>
                )}
                {(p.lifecycle_state === "ACTIVE" || p.lifecycle_state === "ARCHIVED") && (
                  <button title="Clone" onClick={() => setCloneTarget(p)} className="rounded border border-gray-200 p-1.5 text-gray-500 hover:bg-gray-50"><Copy size={14} /></button>
                )}
              </div>
            </Card>
          ))}
          {projects.length === 0 && (
            <Card className="px-6 py-12 text-center text-sm text-gray-500">No {tab.toLowerCase()} projects.</Card>
          )}
        </div>
      )}

      {showNew && (
        <NewProjectModal
          onClose={() => setShowNew(false)}
          onCreated={(p) => { setShowNew(false); navigate(`/projects/${p.id}`); }}
        />
      )}
      {cloneTarget && (
        <CloneModal project={cloneTarget} onClose={() => setCloneTarget(null)}
          onDone={(res) => { setCloneTarget(null); setMsg(`Cloned → ${res.name} (${res.key}).`); load(); }} />
      )}
      {deleteTarget && (
        <DeleteModal project={deleteTarget} onClose={() => setDeleteTarget(null)}
          onDone={(res) => { setDeleteTarget(null); setMsg(`Deleted (${res.lifecycle_state}).`); load(); }} />
      )}
    </div>
  );
}
