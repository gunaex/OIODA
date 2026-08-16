import { useEffect, useState } from "react";
import { documentApi } from "../api";
import { Badge } from "../components/ui";

const CLASSIFICATIONS = [
  "LET OIDA SUGGEST",
  "CLARIFICATION",
  "CORRECTION",
  "REQUIREMENT_CHANGE",
  "SCOPE_EXPANSION",
  "CHANGE_REQUEST",
];

export default function NewChangeRequestModal({ projectId, onClose, onCreated }) {
  const [form, setForm] = useState({
    title: "",
    requested_change: "",
    requested_by: "Owner",
    requested_date: new Date().toISOString().slice(0, 10),
    reason: "",
    source_reference: "",
    notes: "",
    classification: "LET OIDA SUGGEST",
  });
  const [affected, setAffected] = useState([]);
  const [requirements, setRequirements] = useState([]);
  const [suggestion, setSuggestion] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    documentApi.listRequirements(projectId).then(setRequirements).catch(() => setRequirements([]));
  }, [projectId]);

  useEffect(() => {
    if (form.classification !== "LET OIDA SUGGEST") {
      setSuggestion(null);
      return;
    }
    if (affected.length === 0) {
      setSuggestion(null);
      return;
    }
    documentApi
      .suggestCrClassification(projectId, affected)
      .then(setSuggestion)
      .catch(() => setSuggestion(null));
  }, [affected, form.classification, projectId]);

  function set(key, value) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function toggleAffected(code) {
    setAffected((a) => (a.includes(code) ? a.filter((c) => c !== code) : [...a, code]));
  }

  function acceptSuggestion() {
    if (suggestion) set("classification", suggestion.classification);
  }

  async function save() {
    if (!form.requested_change.trim()) {
      setError("Requested change is required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const payload = {
        project_id: projectId,
        requested_change: form.requested_change,
        title: form.title || null,
        requested_by: form.requested_by,
        requested_date: form.requested_date,
        reason: form.reason || null,
        source_reference: form.source_reference || null,
        notes: form.notes || null,
        affected_semantic_ids: affected,
        classification:
          form.classification === "LET OIDA SUGGEST" ? suggestion?.classification || null : form.classification,
      };
      const created = await documentApi.createChangeRequest(payload);
      onCreated?.(created);
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setBusy(false);
    }
  }

  const classificationShown =
    form.classification === "LET OIDA SUGGEST" ? suggestion?.classification || "—" : form.classification;

  return (
    <div className="fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-black/30 p-6" onClick={onClose}>
      <div className="mt-8 w-full max-w-2xl rounded-xl border border-gray-200 bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold">New Change Request</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700">✕</button>
        </div>
        <p className="mt-1 text-xs text-gray-500">
          Saved as a <Badge tone="amber">DRAFT</Badge> — never alters requirements, baselines, PM, QA or Infra.
        </p>

        <div className="mt-4 grid gap-3">
          <Field label="Title">
            <input className="input" value={form.title} onChange={(e) => set("title", e.target.value)} placeholder="e.g. Add DR Environment" />
          </Field>
          <Field label="Requested change *">
            <textarea className="input min-h-20" value={form.requested_change} onChange={(e) => set("requested_change", e.target.value)} placeholder="Describe the requested change" />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Requested by">
              <input className="input" value={form.requested_by} onChange={(e) => set("requested_by", e.target.value)} />
            </Field>
            <Field label="Requested date">
              <input type="date" className="input" value={form.requested_date} onChange={(e) => set("requested_date", e.target.value)} />
            </Field>
          </div>
          <Field label="Reason / business justification">
            <textarea className="input min-h-16" value={form.reason} onChange={(e) => set("reason", e.target.value)} placeholder="Why is this change needed?" />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Source / reference">
              <input className="input" value={form.source_reference} onChange={(e) => set("source_reference", e.target.value)} placeholder="Contract, email, ticket…" />
            </Field>
            <Field label="Classification">
              <select className="input" value={form.classification} onChange={(e) => set("classification", e.target.value)}>
                {CLASSIFICATIONS.map((c) => (
                  <option key={c} value={c}>{c === "LET OIDA SUGGEST" ? "LET OIDA SUGGEST (default)" : c}</option>
                ))}
              </select>
            </Field>
          </div>

          {form.classification === "LET OIDA SUGGEST" && suggestion && (
            <div className="rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-sm">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-violet-500">Suggested classification</span>
                <Badge tone="violet">{suggestion.classification}</Badge>
              </div>
              <div className="mt-1 text-gray-700">{suggestion.reason}</div>
              <div className="mt-0.5 text-xs text-gray-500">Confidence: {suggestion.confidence} · {suggestion.basis}</div>
              <button onClick={acceptSuggestion} className="mt-2 rounded-lg border border-violet-300 bg-white px-3 py-1 text-xs font-medium text-violet-700 hover:bg-violet-100">
                Accept suggestion
              </button>
            </div>
          )}

          <Field label="Affected objects (optional)">
            <div className="rounded-lg border border-gray-200 p-2">
              <div className="mb-1 text-xs text-gray-500">
                Selected: {affected.length === 0 ? "none" : affected.join(", ")} — classification is suggested from these.
              </div>
              <div className="max-h-32 overflow-y-auto">
                {requirements.map((r) => (
                  <label key={r.id} className="flex items-center gap-2 py-0.5 text-sm">
                    <input type="checkbox" checked={affected.includes(r.code)} onChange={() => toggleAffected(r.code)} />
                    <span className="font-mono text-xs text-gray-600">{r.code}</span>
                    <span className="truncate text-gray-700">{r.title}</span>
                  </label>
                ))}
                {requirements.length === 0 && <div className="text-xs text-gray-400">No requirements found.</div>}
              </div>
            </div>
          </Field>

          <Field label="Notes">
            <textarea className="input min-h-16" value={form.notes} onChange={(e) => set("notes", e.target.value)} placeholder="Any additional notes" />
          </Field>
        </div>

        {error && <div className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-600">{error}</div>}

        <div className="mt-4 flex items-center justify-between border-t border-gray-100 pt-3">
          <div className="text-xs text-gray-400">
            Will be created as {classificationShown === "—" ? "unclassified" : classificationShown}.
          </div>
          <div className="flex gap-2">
            <button onClick={onClose} className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50">Cancel</button>
            <button onClick={save} disabled={busy} className="rounded-lg bg-gray-900 px-4 py-1.5 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50">
              {busy ? "Saving…" : "Save Draft"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-xs font-medium text-gray-600">{label}</span>
      {children}
    </label>
  );
}
