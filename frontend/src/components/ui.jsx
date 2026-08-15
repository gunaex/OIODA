import React from "react";

/* Shared ecosystem-grammar primitives: badges, buttons, cards, panels. */

const STATUS_CLASS = {
  DRAFT: "bg-slate-500/15 text-status-draft border-slate-500/30",
  IN_REVIEW: "bg-amber-500/15 text-status-review border-amber-500/30",
  CONFIRMED: "bg-emerald-500/15 text-status-confirmed border-emerald-500/30",
  SUPERSEDED: "bg-slate-500/10 text-status-superseded border-slate-600/30",
  ARCHIVED: "bg-slate-500/10 text-status-archived border-slate-700/30",
  OPEN: "bg-amber-500/15 text-status-open border-amber-500/30",
  RESOLVED: "bg-emerald-500/15 text-status-resolved border-emerald-500/30",
  BLOCKED: "bg-red-500/15 text-status-blocked border-red-500/30",
  IMPLEMENTED: "bg-emerald-500/15 text-status-confirmed border-emerald-500/30",
  ACCEPTED: "bg-emerald-500/15 text-status-confirmed border-emerald-500/30",
  REJECTED: "bg-red-500/15 text-status-fail border-red-500/30",
  PASS: "bg-emerald-500/15 text-status-confirmed border-emerald-500/30",
  FAIL: "bg-red-500/15 text-status-fail border-red-500/30",
};

export function StatusBadge({ status }) {
  const cls = STATUS_CLASS[status] || STATUS_CLASS.DRAFT;
  return (
    <span className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[11px] font-medium tracking-wide ${cls}`}>
      {String(status).replaceAll("_", " ")}
    </span>
  );
}

export function Button({ children, variant = "default", className = "", ...props }) {
  const styles = {
    default: "bg-surface-3 hover:bg-line text-slate-200 border border-line",
    primary: "bg-brand-600 hover:bg-brand-500 text-white border border-brand-500",
    danger: "bg-red-600/90 hover:bg-red-500 text-white border border-red-500",
    ghost: "hover:bg-surface-2 text-slate-400 border border-transparent",
  };
  return (
    <button
      className={`rounded px-2.5 py-1 text-[13px] font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${styles[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

export function Card({ title, actions, children, className = "" }) {
  return (
    <section className={`rounded-lg border border-line bg-surface-1 ${className}`}>
      {title && (
        <header className="flex items-center justify-between border-b border-line px-4 py-2.5">
          <h2 className="text-[13px] font-semibold tracking-wide text-slate-300">{title}</h2>
          <div className="flex items-center gap-2">{actions}</div>
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Empty({ children }) {
  return <p className="py-8 text-center text-[13px] text-slate-500">{children}</p>;
}

export function ErrorNote({ error }) {
  if (!error) return null;
  return (
    <p className="rounded border border-red-500/40 bg-red-500/10 px-3 py-2 text-[12px] text-red-300">
      {String(error.message || error)}
    </p>
  );
}

export function Field({ label, children }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[11px] font-medium uppercase tracking-wider text-slate-500">{label}</span>
      {children}
    </label>
  );
}

export const inputClass =
  "rounded border border-line bg-surface-0 px-2.5 py-1.5 text-[13px] text-slate-200 outline-none focus:border-brand-500";

export function Modal({ title, open, onClose, children, footer }) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onMouseDown={onClose}
    >
      <div
        className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-lg border border-line bg-surface-1 shadow-xl"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <header className="sticky top-0 flex items-center justify-between border-b border-line bg-surface-1 px-4 py-3">
          <h3 className="text-[14px] font-semibold text-slate-200">{title}</h3>
          <button className="text-slate-500 hover:text-slate-300" onClick={onClose}>✕</button>
        </header>
        <div className="p-4">{children}</div>
        {footer && <footer className="flex justify-end gap-2 border-t border-line px-4 py-3">{footer}</footer>}
      </div>
    </div>
  );
}

/*
 * Shared confirmation dialog — one interaction for the whole workspace.
 * Captures comment + evidence; confirmation is never a silent one-click.
 */
export function ConfirmDialog({ open, revision, onClose, onConfirm, busy, error }) {
  const [comment, setComment] = React.useState("");
  const [evidence, setEvidence] = React.useState("");
  const [evidenceError, setEvidenceError] = React.useState(null);

  React.useEffect(() => {
    if (open) { setComment(""); setEvidence(""); setEvidenceError(null); }
  }, [open]);

  function submit() {
    let ev = null;
    if (evidence.trim()) {
      try { ev = JSON.parse(evidence); }
      catch { setEvidenceError("Evidence must be valid JSON (or empty)"); return; }
    }
    onConfirm({ comment: comment.trim() || null, evidence: ev });
  }

  return (
    <Modal
      title="Confirm revision"
      open={open}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" disabled={busy} onClick={submit}>Confirm (immutable)</Button>
        </>
      }
    >
      <div className="space-y-3">
        <p className="text-[13px] text-slate-300">
          {revision?.artifact_title || revision?.title} · r{revision?.revision_number}
          {" "}— confirming makes this revision immutable. To change it later you must clone a new revision.
        </p>
        <label className="flex flex-col gap-1">
          <span className="text-[11px] font-medium uppercase tracking-wider text-slate-500">Confirmation comment</span>
          <textarea className={`${inputClass} min-h-16 w-full`} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="e.g. UR reviewed and approved" />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[11px] font-medium uppercase tracking-wider text-slate-500">Evidence (JSON, optional)</span>
          <textarea className={`${inputClass} min-h-16 w-full font-mono text-[12px]`} value={evidence} onChange={(e) => setEvidence(e.target.value)} placeholder='{"review": "walkthrough"}' />
          {evidenceError && <span className="text-[12px] text-red-400">{evidenceError}</span>}
        </label>
        {error && <p className="text-[12px] text-red-400">{error.message || error}</p>}
      </div>
    </Modal>
  );
}
