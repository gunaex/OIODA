import { useEffect, useMemo, useState } from "react";
import { humanApi } from "../api";
import { API_BASE } from "../api/client";
import { useProjectCtx } from "../hooks/useProject";
import { canRetryAi, impactSections, isAiGuidanceCurrent, routedActionForReview, validCitations } from "../lib/reviewer";
import { impactResolutionFromActionResult } from "../lib/actionResult";
import {
  Card, CardHeader, StatCard, Table, Tr, Td, Badge, Loading, OidaError, formatDateTime,
} from "../components/ui";
import {
  Download, RefreshCw, Stamp, Sparkles,
} from "lucide-react";

const APPL_TONE = { MANDATORY: "rose", RECOMMENDED: "amber", CONDITIONAL: "gray", OPTIONAL: "gray" };
const LIFE_TONE = {
  NOT_GENERATED: "gray", DRAFT: "amber", INTERNAL_REVIEW: "blue", CUSTOMER_REVIEW: "blue",
  APPROVED: "green", BASELINED: "emerald", SUPERSEDED: "gray", ARCHIVED: "gray",
};
const READY_TONE = {
  READY: "emerald", READY_WITH_GAPS: "amber", NOT_READY: "rose", BLOCKED: "rose", NOT_DUE: "gray",
};
const FRESH_TONE = { CURRENT: "emerald", STALE: "rose", UNKNOWN: "gray", NOT_APPLICABLE: "gray" };
const ROLE_TONE = { OWNER: "violet", REVIEWER: "blue", APPROVER: "amber", SIGNATORY: "rose", FYI: "gray" };
const LEVEL_TONE = { CONTROLLED: "rose", WORKING: "amber", REGISTER: "gray" };
const SEV_TONE = {
  INFO: "gray", RECOMMENDED: "blue", STRONGLY_RECOMMENDED: "amber",
  LEGAL_STRONGLY_REQUIRED: "rose", CRITICAL_RISK: "rose",
};
const GATE_TONE = {
  ACCEPTED: "emerald", ACCEPTED_WITH_EXCEPTIONS: "amber", AWAITING_CUSTOMER_ACCEPTANCE: "amber",
  INTERNAL_COMPLETE: "blue", TEST_EVIDENCE_PRESENT: "gray", OPEN: "rose",
  WAIVED: "gray", NOT_APPLICABLE: "gray", NOT_DUE: "gray",
};
const EVIDENCE_TONE = { TEST: "gray", INTERNAL: "blue", CUSTOMER: "emerald", FORMAL_EXTERNAL: "violet" };

const FILTERS = ["All", "My Actions", "Ready", "Needs Information", "Generated", "Mandatory", "Not Due"];

const SOURCE_ROUTE = {
  DOCUMENT_AGAIN: "requirements",
  PM_AGAIN: "planning",
  QA_AGAIN: "qa",
  INFRA_AGAIN: "architecture",
  ACCOUNT_AGAIN: "account",
  CONDUCTOR_AGAIN: "conductor",
};

function SectionState({ state }) {
  const tone = { READY: "green", PARTIAL: "amber", BLOCKED: "red", UNKNOWN: "amber", MISSING: "red", NO_SOURCE: "gray" }[state] || "gray";
  return <Badge tone={tone}>{state}</Badge>;
}

export default function Deliverables() {
  const { project } = useProjectCtx();
  const [catalog, setCatalog] = useState(null);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState("All");
  const [tab, setTab] = useState("Documents");
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [signoffForm, setSignoffForm] = useState({ decision: "ACCEPT", comment: "", signer_role: "", exceptions: "", evidence_class: "CUSTOMER", purpose: "ACCEPTANCE" });
  const [brief, setBrief] = useState(null);
  const [reviewEvidence, setReviewEvidence] = useState(null);
  const [reviewEvidenceError, setReviewEvidenceError] = useState(null);
  const [aiGuidance, setAiGuidance] = useState(null);
  const [aiStatus, setAiStatus] = useState(null);
  const [aiBusy, setAiBusy] = useState(false);
  const [showAi, setShowAi] = useState(false);
  const [actionPreview, setActionPreview] = useState(null);
  const [actionResult, setActionResult] = useState(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [resolveForm, setResolveForm] = useState({ gate: null, reason: "" });

  const base = `/projects/${project?.id}`;

  async function load() {
    if (!project) return;
    setBusy(true); setError(null);
    try {
      const [c, d] = await Promise.all([humanApi.catalog(), humanApi.list(project.id)]);
      setCatalog(c); setData(d);
    } catch (e) { setError(e.message || String(e)); }
    finally { setBusy(false); }
  }
  useEffect(() => { load(); }, [project?.id]);

  async function openDetail(code) {
    setSelected(code); setError(null); setBusy(true);
    setReviewEvidence(null); setReviewEvidenceError(null); setAiGuidance(null); setAiStatus(null); setShowAi(false);
    setActionPreview(null); setActionResult(null);
    try {
      const d = await humanApi.detail(project.id, code);
      setDetail(d);
      if (d.instance) {
        humanApi.aiStatus().then(setAiStatus).catch(() => setAiStatus({ status: "AI_UNAVAILABLE", message: "AI status is unavailable. Deterministic review is ready." }));
        humanApi.reviewerEvidence(project.id, code, signoffForm.signer_role || undefined, signoffForm.purpose)
          .then(setReviewEvidence)
          .catch((e) => setReviewEvidenceError(e.message || String(e)));
      }
    } catch (e) { setError(e.message || String(e)); }
    finally { setBusy(false); }
  }

  async function refreshDetail() {
    if (!selected) return;
    try {
      const d = await humanApi.detail(project.id, selected);
      setDetail(d);
    } catch (e) { setError(e.message || String(e)); }
  }

  async function runPrecheck() {
    setBusy(true);
    try {
      await humanApi.precheck(project.id, selected);
      await refreshDetail(); await load();
    } catch (e) { setError(e.message || String(e)); }
    finally { setBusy(false); }
  }

  async function generate(withGaps) {
    setBusy(true);
    try {
      await humanApi.generate(project.id, selected, { with_gaps: withGaps });
      await refreshDetail(); await load();
    } catch (e) { setError(e.message || String(e)); }
    finally { setBusy(false); }
  }

  async function transition(target) {
    setBusy(true);
    try {
      await humanApi.transition(project.id, selected, { target });
      await refreshDetail(); await load();
    } catch (e) { setError(e.message || String(e)); }
    finally { setBusy(false); }
  }

  async function doSignoff() {
    setBusy(true);
    try {
      const exceptions = signoffForm.exceptions.trim()
        ? signoffForm.exceptions.split("\n").map((line) => {
            const [item, owner, due] = line.split("|").map((s) => s.trim());
            return { item: item || line, owner: owner || "", due: due || "" };
          })
        : [];
      await humanApi.signoff(project.id, selected, {
        decision: signoffForm.decision,
        evidence_class: signoffForm.evidence_class,
        purpose: signoffForm.purpose,
        comment: signoffForm.comment || null,
        signer_role: signoffForm.signer_role || null,
        known_exceptions: exceptions,
      });
      setSignoffForm({ decision: "ACCEPT", comment: "", signer_role: "", exceptions: "", evidence_class: "CUSTOMER", purpose: "ACCEPTANCE" });
      await refreshDetail(); await load();
    } catch (e) { setError(e.message || String(e)); }
    finally { setBusy(false); }
  }

  async function fetchBrief() {
    try {
      const b = await humanApi.brief(project.id, selected, signoffForm.signer_role || undefined);
      setBrief(b);
    } catch (e) { setBrief(null); }
  }

  async function refreshReviewerEvidence() {
    setReviewEvidenceError(null);
    try {
      const packet = await humanApi.reviewerEvidence(project.id, selected, signoffForm.signer_role || undefined, signoffForm.purpose);
      setReviewEvidence(packet);
      if (aiGuidance && !isAiGuidanceCurrent(packet, aiGuidance)) setAiGuidance(null);
    } catch (e) { setReviewEvidenceError(e.message || String(e)); }
  }

  async function loadAiGuidance(force = false) {
    setShowAi(true); setAiBusy(true);
    try {
      const guidance = await humanApi.aiReviewer(project.id, selected, {
        role: signoffForm.signer_role || null, purpose: signoffForm.purpose, force,
      });
      setAiGuidance(guidance);
    } catch (e) {
      setAiGuidance({ status: "UNAVAILABLE", message: e.message || "AI guidance is unavailable. Deterministic review remains available." });
    } finally { setAiBusy(false); }
  }

  async function reviewImpactRelationship(relationship, decision, impactCandidateId = null, evidenceRefs = []) {
    const reason = decision === "REJECTED"
      ? window.prompt("Why is this relationship incorrect? A reason is required.")
      : decision === "UNRESOLVED"
        ? window.prompt("Optional: what evidence is still needed?")
        : window.prompt("Optional: why is this relationship relevant?");
    if (decision === "REJECTED" && !reason?.trim()) return;
    setBusy(true); setError(null);
    try {
      await humanApi.reviewImpact(project.id, selected, {
        relationship, evidence_hash: reviewEvidence.evidence_packet_hash,
        impact_candidate_id: impactCandidateId, decision, reason: reason || null,
        actor_role: signoffForm.signer_role || null, evidence_refs: evidenceRefs,
        change_id: reviewEvidence.change_impact?.source_change?.change_id || null,
      });
      await refreshReviewerEvidence();
    } catch (e) { setError(e.message || String(e)); }
    finally { setBusy(false); }
  }

  async function previewRoutedAction(review) {
    const actionType = routedActionForReview(review);
    if (!actionType) return;
    setActionBusy(true); setActionResult(null);
    try {
      const preview = await humanApi.previewImpactAction(project.id, selected, {
        action_type: actionType, confirmation_id: review.confirmation_id,
        evidence_hash: reviewEvidence.evidence_packet_hash, parameters: {},
      });
      setActionPreview(preview);
    } catch (e) { setActionResult({ status: "FAILED", failure_detail: e.message || String(e) }); }
    finally { setActionBusy(false); }
  }

  async function executeRoutedAction() {
    if (!actionPreview?.executable) return;
    setActionBusy(true);
    try {
      const result = await humanApi.executeImpactAction(project.id, selected, {
        action_type: actionPreview.action_type, confirmation_id: actionPreview.confirmation_id,
        evidence_hash: reviewEvidence.evidence_packet_hash, parameters: actionPreview.parameters || {},
      });
      if (result.impact_resolution) result.resolution = result.impact_resolution;
      setActionResult(result); setActionPreview(null);
      await refreshReviewerEvidence();
    } catch (e) { setActionResult({ status: "FAILED", failure_detail: e.message || String(e) }); }
    finally { setActionBusy(false); }
  }

  async function recheckImpactResolution(confirmationId) {
    setActionBusy(true); setActionResult(null);
    try {
      const resolution = await humanApi.recheckImpactResolution(project.id, selected, {
        confirmation_id: confirmationId, evidence_hash: reviewEvidence.evidence_packet_hash,
      });
      setActionResult({ status: "RECHECKED", resolution });
      await refreshReviewerEvidence();
    } catch (e) { setActionResult({ status: "FAILED", failure_detail: e.message || String(e) }); }
    finally { setActionBusy(false); }
  }

  async function doResolve() {
    if (!resolveForm.gate || !resolveForm.reason.trim()) return;
    setBusy(true);
    try {
      await humanApi.resolveGate(project.id, resolveForm.gate, {
        resolution_type: resolveForm.type,
        reason: resolveForm.reason,
        actor_role: resolveForm.actor_role || null,
        scope: resolveForm.scope || null,
      });
      setResolveForm({ gate: null, reason: "" });
      await load();
    } catch (e) { setError(e.message || String(e)); }
    finally { setBusy(false); }
  }

  async function download(kind, code) {
    const path = humanApi.exportUrl(project.id, kind, code);
    if (!path) return;
    // exportUrl returns an API-relative path; it must be resolved against the
    // API gateway origin, not the Pages origin (otherwise the SPA fallback
    // returns index.html).
    const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
    const token = localStorage.getItem("oida_ecosystem_token");
    const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      setError(`Download failed (HTTP ${res.status})${text ? `: ${text.slice(0, 120)}` : ""}`);
      return;
    }
    const blob = await res.blob();
    const disposition = res.headers.get("content-disposition") || "";
    const match = disposition.match(/filename="?([^";]+)"?/);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = match ? match[1] : `${project.key}-${kind || "export"}.xlsx`;
    a.click();
  }

  const rows = useMemo(() => {
    if (!data) return [];
    const docs = data.documents;
    if (filter === "All") return docs;
    if (filter === "My Actions") return docs.filter((d) => d.needs_review || d.needs_approval || d.needs_signoff);
    if (filter === "Ready") return docs.filter((d) => d.lifecycle_status === "NOT_GENERATED" && d.readiness === "READY");
    if (filter === "Needs Information") return docs.filter((d) => d.readiness === "NOT_READY" || d.readiness === "READY_WITH_GAPS");
    if (filter === "Generated") return docs.filter((d) => d.lifecycle_status !== "NOT_GENERATED");
    if (filter === "Mandatory") return docs.filter((d) => d.applicability === "MANDATORY");
    if (filter === "Not Due") return docs.filter((d) => d.readiness === "NOT_DUE");
    return docs;
  }, [data, filter]);

  if (!project) return <Loading />;
  if (error && !data) return <OidaError message={String(error)} onRetry={load} />;

  const inst = detail?.instance;
  const pc = detail?.precheck;

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold">Project Documents</h1>
          <p className="text-sm text-gray-500">
            {data ? `${data.project_name} — current phase: ${data.current_phase}. ` : ""}
            You see documents, not standards. {catalog ? `${catalog.internal_module_count} internal standards stay behind the scenes.` : ""}
          </p>
        </div>
        <button onClick={load} disabled={busy}
          className="inline-flex items-center gap-1 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm hover:bg-gray-50 disabled:opacity-50">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      <div className="flex flex-wrap gap-1 border-b border-gray-200 pb-2">
        {["Documents", "Sign-off Register", "My Sign-offs", "Audit Trail"].map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`rounded px-3 py-1.5 text-sm ${tab === t ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}>
            {t}
          </button>
        ))}
      </div>

      {tab === "Documents" && data && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <StatCard label="Need My Review" value={data.my_actions.review} tone="blue" />
            <StatCard label="Need My Approval" value={data.my_actions.approval} tone="amber" />
            <StatCard label="Need My Sign-off" value={data.my_actions.signoff} tone="rose" />
            <StatCard label="Governance Flags" value={data.my_actions.governance_flags ?? 0} tone="rose" />
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <StatCard label="Ready to Generate" value={data.summary.ready_to_generate} tone="emerald" />
            <StatCard label="Needs Information" value={data.summary.needs_information} tone="amber" />
            <StatCard label="Generated" value={data.summary.generated} tone="blue" />
            <StatCard label="Not Due" value={data.summary.not_due} tone="gray" />
            <StatCard label="Stale" value={data.summary.stale} tone="rose" />
          </div>

          {/* Governance & Legal Flags */}
          {data.governance_flags?.length > 0 && (
            <Card>
              <CardHeader title="Governance & Legal Flags" subtitle="Warn strongly — never hard-lock. Humans decide and the decision is recorded." />
              <div className="space-y-2 p-4">
                {data.governance_flags.map((f) => (
                  <div key={f.flag_id} className={`rounded-lg border p-3 ${f.severity === "LEGAL_STRONGLY_REQUIRED" || f.severity === "CRITICAL_RISK" ? "border-rose-300 bg-rose-50" : "border-amber-200 bg-amber-50"}`}>
                    <div className="flex items-center gap-2 text-sm">
                      <span className="font-bold text-rose-600">⚠ {f.severity.replace(/_/g, " ")}</span>
                      <Badge tone={f.status === "ACKNOWLEDGED" ? "amber" : "rose"}>{f.status}</Badge>
                    </div>
                    <div className="mt-1 text-sm font-medium">{f.reason}</div>
                    {f.why && <div className="mt-1 text-xs text-gray-600">Why this matters: {f.why}</div>}
                    {!f.subdued && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        <button onClick={() => setResolveForm({ gate: f.gate, reason: "", type: "PROCEED_WITH_RISK" })}
                          className="rounded border border-rose-300 bg-white px-2 py-1 text-xs text-rose-700 hover:bg-rose-100">Proceed With Risk</button>
                        <button onClick={() => setResolveForm({ gate: f.gate, reason: "", type: "WAIVED" })}
                          className="rounded border border-gray-300 bg-white px-2 py-1 text-xs hover:bg-gray-50">Use Company Policy Exception</button>
                        <button onClick={() => setResolveForm({ gate: f.gate, reason: "", type: "NOT_APPLICABLE" })}
                          className="rounded border border-gray-300 bg-white px-2 py-1 text-xs hover:bg-gray-50">Not Applicable</button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* critical gates */}
          {data.gates?.length > 0 && (
            <Card>
              <CardHeader title="Critical Sign-off Gates" subtitle="Recalculated from evidence class — TEST evidence never qualifies customer acceptance." />
              <div className="flex flex-wrap gap-2 p-4">
                {data.gates.map((g) => (
                  <span key={g.gate} className={`inline-flex flex-col gap-1 rounded-lg border px-2.5 py-1.5 text-xs ${g.flag?.raised && !g.subdued ? "border-rose-300 bg-rose-50" : "border-gray-200 bg-gray-50"}`}>
                    <span className="flex items-center gap-1.5">
                      <span className="font-medium">{g.name}</span>
                      {g.flag?.raised && !g.subdued && <span className="font-bold text-rose-600">⚠</span>}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Badge tone={GATE_TONE[g.status] || "gray"}>{g.status.replace(/_/g, " ")}</Badge>
                      <Badge tone={SEV_TONE[g.severity] || "gray"}>{g.severity.replace(/_/g, " ")}</Badge>
                    </span>
                  </span>
                ))}
              </div>
            </Card>
          )}

          {/* resolve modal */}
          {resolveForm.gate && (
            <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4" onClick={() => setResolveForm({ gate: null, reason: "" })}>
              <div className="w-full max-w-md rounded-xl bg-white p-5" onClick={(e) => e.stopPropagation()}>
                <h3 className="mb-2 text-sm font-bold">
                  {resolveForm.type === "PROCEED_WITH_RISK" ? "Proceed With Risk" : resolveForm.type === "WAIVED" ? "Company Policy Exception" : "Mark Not Applicable"}
                </h3>
                <div className="mb-2 text-xs text-gray-500">
                  {resolveForm.type === "PROCEED_WITH_RISK"
                    ? "Proceeding is allowed, but this governance risk will remain recorded. This is NOT acceptance."
                    : resolveForm.type === "WAIVED"
                    ? "Record a company-policy waiver. This is NOT acceptance."
                    : "Record that this gate does not apply to this project."}
                </div>
                <label className="mb-1 block text-xs font-medium text-gray-600">Reason (required)</label>
                <textarea value={resolveForm.reason} onChange={(e) => setResolveForm({ ...resolveForm, reason: e.target.value })}
                  rows={3} className="w-full rounded-lg border border-gray-300 px-2 py-1.5 text-sm" placeholder="Why is this decision being made?" />
                <label className="mb-1 mt-2 block text-xs font-medium text-gray-600">Decision Owner Role</label>
                <input value={resolveForm.actor_role || ""} onChange={(e) => setResolveForm({ ...resolveForm, actor_role: e.target.value })}
                  className="w-full rounded-lg border border-gray-300 px-2 py-1.5 text-sm" placeholder="e.g. PROJECT_MANAGER" />
                <div className="mt-3 flex justify-end gap-2">
                  <button onClick={() => setResolveForm({ gate: null, reason: "" })} className="rounded-lg border border-gray-300 px-3 py-2 text-sm hover:bg-gray-50">Cancel</button>
                  <button onClick={doResolve} disabled={busy || !resolveForm.reason.trim()}
                    className="rounded-lg bg-gray-900 px-3 py-2 text-sm text-white hover:bg-gray-700 disabled:opacity-50">Record Decision</button>
                </div>
              </div>
            </div>
          )}

          <div className="flex flex-wrap gap-1">
            {FILTERS.map((f) => (
              <button key={f} onClick={() => setFilter(f)}
                className={`rounded px-2 py-1 text-xs ${filter === f ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}>
                {f}
              </button>
            ))}
          </div>

          <Card>
            <CardHeader title="Documents" subtitle={`${rows.length} visible documents`} />
            <Table head={["Document", "Level", "Applies", "Required By", "Readiness", "Lifecycle", "Version", "My Role"]}>
              {rows.map((d) => (
                <Tr key={d.code} onClick={() => openDetail(d.code)} className="cursor-pointer hover:bg-gray-50">
                  <Td>
                    <div className="font-medium">{d.name}</div>
                    <div className="text-xs text-gray-400">{d.code}{d.generated_at ? ` · generated ${formatDateTime(d.generated_at)} by ${d.generated_by}` : ""}</div>
                    {d.governance_flag && (
                      <div className="mt-1 inline-flex items-center gap-1 rounded bg-rose-50 px-1.5 py-0.5 text-[10px] font-bold text-rose-700">
                        ⚠ {d.governance_flag.severity} — {d.governance_flag.reason}
                      </div>
                    )}
                    {d.material_change_flag && (
                      <div className="mt-1 inline-flex items-center gap-1 rounded bg-rose-50 px-1.5 py-0.5 text-[10px] font-bold text-rose-700">
                        ⚠ Material change — re-acceptance recommended
                      </div>
                    )}
                    {d.needs_review && <Badge tone="blue">Needs my review</Badge>}
                    {d.needs_approval && <Badge tone="amber">Needs my approval</Badge>}
                    {d.needs_signoff && <Badge tone="rose">Needs my sign-off</Badge>}
                  </Td>
                  <Td><Badge tone={LEVEL_TONE[d.level_name] || "gray"}>{d.level_name}</Badge></Td>
                  <Td><Badge tone={APPL_TONE[d.applicability] || "gray"}>{d.applicability}</Badge></Td>
                  <Td><div className="text-xs">{d.required_by?.replace(/_/g, " ")}</div></Td>
                  <Td>{d.readiness ? <Badge tone={READY_TONE[d.readiness] || "gray"}>{d.readiness.replace(/_/g, " ")}</Badge> : "—"}</Td>
                  <Td><Badge tone={LIFE_TONE[d.lifecycle_status] || "gray"}>{d.lifecycle_status.replace(/_/g, " ")}</Badge></Td>
                  <Td>{d.version || "—"}</Td>
                  <Td><Badge tone={ROLE_TONE[d.my_role] || "gray"}>{d.my_role}</Badge></Td>
                </Tr>
              ))}
            </Table>
          </Card>

          <Card>
            <CardHeader title="Exports" subtitle="Generated documents, evidence and the acceptance package." />
            <div className="flex flex-wrap gap-2 p-4">
              <button onClick={() => download("signoff-evidence")} className="inline-flex items-center gap-1 rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs hover:bg-gray-50"><Download size={13} /> Sign-off Evidence (JSON)</button>
              <button onClick={() => download("governance-flag-register")} className="inline-flex items-center gap-1 rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs hover:bg-gray-50"><Download size={13} /> Governance Flag Register (.xlsx)</button>
              <button onClick={() => download("risk-overrides")} className="inline-flex items-center gap-1 rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs hover:bg-gray-50"><Download size={13} /> Risk Overrides / Waivers (JSON)</button>
              <button onClick={() => download("acceptance-package")} className="inline-flex items-center gap-1 rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs hover:bg-gray-50"><Download size={13} /> Project Acceptance Package (ZIP)</button>
            </div>
          </Card>
        </>
      )}

      {tab === "Sign-off Register" && <SignoffRegister projectId={project.id} onExport={() => download("signoff-evidence")} />}

      {tab === "My Sign-offs" && <MySignoffs projectId={project.id} />}

      {tab === "Audit Trail" && <AuditTrail projectId={project.id} />}

      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setSelected(null)}>
          <div className="max-h-[88vh] w-full max-w-3xl overflow-auto rounded-xl bg-white p-6" onClick={(e) => e.stopPropagation()}>
            {!detail ? <Loading /> : (
              <>
                <div className="mb-4 flex items-start justify-between">
                  <div>
                    <h2 className="text-lg font-bold">{detail.catalog?.name}</h2>
                    <div className="mt-1 flex flex-wrap gap-2 text-xs text-gray-500">
                      <span>{detail.human_code}</span>
                      <span>·</span><span>{detail.catalog?.level_name}</span>
                      <span>·</span><span>required by {detail.catalog?.required_by?.replace(/_/g, " ")}</span>
                    </div>
                  </div>
                  <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-gray-700">✕</button>
                </div>

                {error && <div className="mb-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{String(error)}</div>}

                <div className="mb-4 grid grid-cols-2 gap-2 rounded-lg bg-gray-50 p-3 text-xs md:grid-cols-3">
                  <div><span className="font-semibold text-gray-500">Owner</span><div>{detail.catalog?.owner_role}</div></div>
                  <div><span className="font-semibold text-gray-500">Reviewers</span><div>{(detail.catalog?.reviewer_roles || []).join(", ") || "—"}</div></div>
                  <div><span className="font-semibold text-gray-500">Approvers</span><div>{(detail.catalog?.approver_roles || []).join(", ") || "—"}</div></div>
                  <div><span className="font-semibold text-gray-500">Signatories</span><div>{(detail.catalog?.signatory_roles || []).join(", ") || "—"}</div></div>
                  <div className="col-span-2"><span className="font-semibold text-gray-500">Sign-off policy</span><div>{detail.catalog?.signoff_policy?.mode} · gate {detail.catalog?.signoff_policy?.gate}</div></div>
                </div>

                {pc && (
                  <div className="mb-4">
                    <div className="mb-2 flex items-center justify-between">
                      <div className="text-sm font-semibold">Generation Precheck</div>
                      <div className="flex items-center gap-2">
                        <Badge tone={READY_TONE[pc.readiness] || "gray"}>{pc.readiness.replace(/_/g, " ")}</Badge>
                        <button onClick={runPrecheck} disabled={busy} className="rounded border border-gray-300 px-2 py-1 text-xs hover:bg-gray-50">Re-run</button>
                      </div>
                    </div>
                    <div className="mb-2 text-xs text-gray-500">
                      {pc.timing_state === "UPCOMING" ? pc.timing_label : `${pc.ready_sections} / ${pc.required_sections} required sections ready`} · {pc.total_modules} internal modules
                    </div>
                    {pc.sections.map((s) => (
                      <div key={s.title} className="mb-2 rounded-lg border border-gray-100 p-2">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-medium">{s.title}</span>
                          <span className="text-gray-400">{s.ready} ready · {s.partial} partial · {s.unknown || 0} unknown · {s.missing} missing</span>
                        </div>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {s.standards.map((std) => (
                            <details key={std.name} className="rounded bg-gray-50 px-1.5 py-0.5 text-[10px]">
                              <summary className="inline-flex cursor-pointer list-none items-center gap-1"><SectionState state={std.state} />{std.name}</summary>
                              {std.reason && <div className="mt-1 max-w-sm text-gray-600">{std.reason}</div>}
                              {std.provenance && <div className="text-gray-400">Source {std.provenance.source_service} · revision {std.provenance.source_revision || "not supplied"} · retrieved {formatDateTime(std.provenance.retrieved_at)}</div>}
                              {std.state !== "READY" && <a href={`${base}/${SOURCE_ROUTE[std.authority] || "requirements"}`} onClick={(e) => e.stopPropagation()} className="text-blue-600 underline">open {std.owner_label}</a>}
                            </details>
                          ))}
                        </div>
                      </div>
                    ))}
                    {pc.cross_service_dependencies?.length > 0 && <div className="mt-3 rounded-lg border border-gray-200 p-2">
                      <div className="mb-1 text-xs font-semibold">Live cross-service dependencies</div>
                      {pc.cross_service_dependencies.map((dep) => <details key={dep.name} className="border-t border-gray-100 py-1 text-xs">
                        <summary className="flex cursor-pointer list-none items-center justify-between"><span>{dep.name} · {dep.authority.replace("_", " ")}</span><SectionState state={dep.state} /></summary>
                        <div className="mt-1 text-gray-600">{dep.reason}</div>
                        {dep.provenance && <div className="text-gray-400">Revision {dep.provenance.source_revision || "not supplied"} · retrieved {formatDateTime(dep.provenance.retrieved_at)}</div>}
                      </details>)}
                    </div>}
                  </div>
                )}

                {!inst && pc && (
                  <div className="mb-4 flex gap-2">
                    <button onClick={() => generate(false)} disabled={busy || pc.readiness === "NOT_DUE"}
                      className="rounded-lg bg-gray-900 px-3 py-2 text-sm text-white hover:bg-gray-700 disabled:opacity-50">
                      {pc.readiness === "READY" ? "Generate Draft" : "Generate Draft With Gaps"}
                    </button>
                    <button onClick={() => setSelected(null)} className="rounded-lg border border-gray-300 px-3 py-2 text-sm hover:bg-gray-50">Cancel</button>
                  </div>
                )}

                {inst && (
                  <>
                    <div className="mb-4 grid grid-cols-2 gap-2 rounded-lg bg-gray-50 p-3 text-xs md:grid-cols-4">
                      <div><span className="font-semibold text-gray-500">Version</span><div>{inst.version}</div></div>
                      <div><span className="font-semibold text-gray-500">Lifecycle</span><div><Badge tone={LIFE_TONE[inst.lifecycle_status] || "gray"}>{inst.lifecycle_status}</Badge></div></div>
                      <div><span className="font-semibold text-gray-500">Generated By</span><div>{inst.generated_by}</div></div>
                      <div><span className="font-semibold text-gray-500">Generated At</span><div>{inst.generated_at ? formatDateTime(inst.generated_at) : "—"}</div></div>
                      <div className="col-span-2"><span className="font-semibold text-gray-500">Content Hash</span><div className="break-all">{inst.snapshot_hash}</div></div>
                      <div><span className="font-semibold text-gray-500">Freshness</span><div><Badge tone={FRESH_TONE[inst.freshness] || "gray"}>{inst.freshness}</Badge></div></div>
                      <div><span className="font-semibold text-gray-500">Material Change</span><div>{inst.material_change}</div></div>
                    </div>

                    <ReviewerChangeBrief
                      packet={reviewEvidence}
                      error={reviewEvidenceError}
                      onRefresh={refreshReviewerEvidence}
                      ai={aiGuidance}
                      aiStatus={aiStatus}
                      aiBusy={aiBusy}
                      showAi={showAi}
                      onShowAi={() => loadAiGuidance(false)}
                      onRefreshAi={() => loadAiGuidance(true)}
                      onHideAi={() => setShowAi(false)}
                      onReviewImpact={reviewImpactRelationship}
                      impactBusy={busy}
                      actionPreview={actionPreview}
                      actionResult={actionResult}
                      actionBusy={actionBusy}
                      onPreviewAction={previewRoutedAction}
                      onExecuteAction={executeRoutedAction}
                      onRecheckResolution={recheckImpactResolution}
                      onCancelAction={() => setActionPreview(null)}
                    />

                    <div className="mb-4 flex flex-wrap gap-2">
                      {inst.lifecycle_status === "DRAFT" && <button onClick={() => transition("INTERNAL_REVIEW")} disabled={busy} className="rounded-lg border border-gray-300 px-3 py-2 text-sm hover:bg-gray-50">Submit for Internal Review</button>}
                      {inst.lifecycle_status === "INTERNAL_REVIEW" && <button onClick={() => transition("CUSTOMER_REVIEW")} disabled={busy} className="rounded-lg border border-gray-300 px-3 py-2 text-sm hover:bg-gray-50">Send to Customer Review</button>}
                      {inst.lifecycle_status === "APPROVED" && <button onClick={() => transition("BASELINED")} disabled={busy} className="rounded-lg border border-gray-300 px-3 py-2 text-sm hover:bg-gray-50">Baseline</button>}
                      {(inst.lifecycle_status === "APPROVED" || inst.lifecycle_status === "BASELINED") && (
                        <button onClick={() => generate(true)} disabled={busy} className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm hover:bg-amber-100">
                          Create Revision (v{inst.version} stays immutable)
                        </button>
                      )}
                    </div>

                    <div className="mb-4 flex flex-wrap gap-2">
                      <button onClick={() => download("human", selected)} className="inline-flex items-center gap-1 rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs hover:bg-gray-50"><Download size={13} /> Controlled Document (.xlsx)</button>
                      <button onClick={() => download("snapshot", selected)} className="inline-flex items-center gap-1 rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs hover:bg-gray-50"><Download size={13} /> Source Snapshot (.json)</button>
                    </div>

                    {(inst.lifecycle_status === "CUSTOMER_REVIEW" || inst.lifecycle_status === "APPROVED") && (
                      <div className="mb-4 rounded-lg border border-gray-200 p-3">
                        <div className="mb-2 text-sm font-semibold">Sign-off — applies only to this exact version (v{inst.version})</div>
                        {detail.signoffs?.length > 0 && (
                          <div className="mb-2 text-xs text-gray-500">Already signed: {detail.signoffs.map((s) => `${s.decision} (${s.evidence_class || "?"}/${s.purpose || "?"}) by ${s.signer_name} v${s.document_version}`).join("; ")}</div>
                        )}

                        {/* responsibility brief */}
                        <div className="mb-3 rounded-lg bg-blue-50 p-3 text-xs">
                          <div className="mb-1 flex items-center justify-between">
                            <span className="font-semibold text-blue-800">Why am I being asked?</span>
                            <button onClick={fetchBrief} className="rounded border border-blue-200 px-2 py-0.5 text-blue-700 hover:bg-blue-100">Refresh</button>
                          </div>
                          {brief ? (
                            <>
                              <div className="font-medium">You are the {brief.role}.</div>
                              <div className="mt-1">You are being asked to confirm: {brief.confirms.join("; ")}.</div>
                              <div className="mt-1 text-gray-600">You are NOT confirming: {brief.excludes.join("; ")}.</div>
                            </>
                          ) : (
                            <div className="text-gray-500">Select a signer role to see your responsibility brief.</div>
                          )}
                        </div>

                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div>
                            <label className="mb-1 block font-medium text-gray-600">Decision</label>
                            <select value={signoffForm.decision} onChange={(e) => setSignoffForm({ ...signoffForm, decision: e.target.value })}
                              className="w-full rounded-lg border border-gray-300 px-2 py-1.5">
                              {["ACCEPT", "ACCEPTED_WITH_EXCEPTIONS", "APPROVE", "ACKNOWLEDGE", "REJECT"].map((d) => <option key={d} value={d}>{d}</option>)}
                            </select>
                          </div>
                          <div>
                            <label className="mb-1 block font-medium text-gray-600">Signer Role</label>
                            <input value={signoffForm.signer_role} onChange={(e) => { setSignoffForm({ ...signoffForm, signer_role: e.target.value }); setBrief(null); }}
                              placeholder="e.g. CUSTOMER_TECHNICAL_OWNER" className="w-full rounded-lg border border-gray-300 px-2 py-1.5" />
                          </div>
                          <div>
                            <label className="mb-1 block font-medium text-gray-600">Evidence Class</label>
                            <select value={signoffForm.evidence_class} onChange={(e) => setSignoffForm({ ...signoffForm, evidence_class: e.target.value })}
                              className="w-full rounded-lg border border-gray-300 px-2 py-1.5">
                              {["CUSTOMER", "INTERNAL", "TEST", "FORMAL_EXTERNAL"].map((c) => <option key={c} value={c}>{c}</option>)}
                            </select>
                            <div className="mt-1 text-[10px] text-gray-400">TEST/INTERNAL never qualify customer acceptance.</div>
                          </div>
                          <div>
                            <label className="mb-1 block font-medium text-gray-600">Purpose</label>
                            <select value={signoffForm.purpose} onChange={(e) => setSignoffForm({ ...signoffForm, purpose: e.target.value })}
                              className="w-full rounded-lg border border-gray-300 px-2 py-1.5">
                              {["ACCEPTANCE", "SIGN_OFF", "APPROVAL", "REVIEW", "ACKNOWLEDGEMENT"].map((p) => <option key={p} value={p}>{p}</option>)}
                            </select>
                          </div>
                          <div className="col-span-2">
                            <label className="mb-1 block font-medium text-gray-600">Comment</label>
                            <textarea value={signoffForm.comment} onChange={(e) => setSignoffForm({ ...signoffForm, comment: e.target.value })}
                              placeholder="Optional" rows={2} className="w-full rounded-lg border border-gray-300 px-2 py-1.5" />
                            <label className="mb-1 mt-2 block font-medium text-gray-600">Known exceptions (one per line: item | owner | due)</label>
                            <textarea value={signoffForm.exceptions} onChange={(e) => setSignoffForm({ ...signoffForm, exceptions: e.target.value })}
                              placeholder={"wave ownership | PM | 2026-08-30"} rows={2} className="w-full rounded-lg border border-gray-300 px-2 py-1.5" />
                          </div>
                        </div>
                        <button onClick={doSignoff} disabled={busy}
                          className="mt-2 inline-flex items-center gap-1 rounded-lg bg-rose-600 px-3 py-2 text-sm font-medium text-white hover:bg-rose-500 disabled:opacity-50">
                          <Stamp size={14} /> Approve & Sign
                        </button>
                      </div>
                    )}

                    {detail.versions?.length > 0 && (
                      <div className="mb-2">
                        <div className="mb-1 text-xs font-semibold text-gray-500">Version History</div>
                        <Table head={["Version", "Lifecycle", "Generated At", "Generated By", "Hash"]}>
                          {detail.versions.map((v) => (
                            <Tr key={v.id}>
                              <Td>{v.version}</Td>
                              <Td><Badge tone={LIFE_TONE[v.lifecycle_status] || "gray"}>{v.lifecycle_status}</Badge></Td>
                              <Td>{v.generated_at ? formatDateTime(v.generated_at) : "—"}</Td>
                              <Td>{v.generated_by || "—"}</Td>
                              <Td><span className="text-xs">{(v.snapshot_hash || "").slice(0, 12)}</span></Td>
                            </Tr>
                          ))}
                        </Table>
                      </div>
                    )}
                  </>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function EvidenceItem({ item }) {
  if (!item) return null;
  return (
    <details id={`review-evidence-${item.evidence_id}`} className="rounded-lg border border-gray-200 bg-white p-2 text-xs">
      <summary className="flex cursor-pointer list-none items-center gap-2">
        <span className="font-mono font-semibold text-blue-700">{item.evidence_id}</span>
        <Badge tone={item.change === "NOT_RECORDED" ? "amber" : item.change === "CURRENT" ? "gray" : "blue"}>{item.change}</Badge>
        <span className="font-medium">{item.summary}</span>
      </summary>
      <div className="mt-2 grid gap-1 border-t border-gray-100 pt-2 text-gray-600">
        <div>Domain: {item.domain} · Source: {item.source}</div>
        {item.path && <div>Path: <span className="font-mono">{item.path}</span></div>}
        {item.before !== null && item.before !== undefined && <div className="break-all">Before: {JSON.stringify(item.before)}</div>}
        {item.after !== null && item.after !== undefined && <div className="break-all">After: {JSON.stringify(item.after)}</div>}
        <div className="break-all">Provenance: {JSON.stringify(item.provenance || {})}</div>
      </div>
    </details>
  );
}

function ImpactReviewButtons({ disabled, onDecision }) {
  return <div className="mt-2 flex flex-wrap gap-1">
    <button disabled={disabled} onClick={() => onDecision("CONFIRMED")} className="rounded border border-emerald-300 bg-emerald-50 px-2 py-1 text-[10px] text-emerald-800 disabled:opacity-50">Confirm Relationship</button>
    <button disabled={disabled} onClick={() => onDecision("REJECTED")} className="rounded border border-rose-300 bg-rose-50 px-2 py-1 text-[10px] text-rose-800 disabled:opacity-50">Reject Relationship</button>
    <button disabled={disabled} onClick={() => onDecision("UNRESOLVED")} className="rounded border border-gray-300 px-2 py-1 text-[10px] text-gray-700 disabled:opacity-50">Leave Unresolved</button>
  </div>;
}

function ReviewerChangeBrief({ packet, error, onRefresh, ai, aiStatus, aiBusy, showAi, onShowAi, onRefreshAi, onHideAi, onReviewImpact, impactBusy, actionPreview, actionResult, actionBusy, onPreviewAction, onExecuteAction, onRecheckResolution, onCancelAction }) {
  if (error) return <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">Reviewer evidence unavailable: {error}. Existing review controls remain available.</div>;
  if (!packet) return <div className="mb-4 rounded-lg border border-gray-200 p-3 text-xs text-gray-500">Preparing deterministic reviewer evidence…</div>;
  const brief = packet.deterministic_brief;
  const byId = Object.fromEntries(packet.evidence_items.map((item) => [item.evidence_id, item]));
  const aiSections = [
    ["Top things to focus on", "focus_items"],
    ["Risks and exceptions", "risks_and_exceptions"],
    ["Questions to consider", "reviewer_questions"],
    ["Suggested reading", "suggested_reading"],
  ];
  const aiCurrent = isAiGuidanceCurrent(packet, ai);
  const aiFailed = canRetryAi(ai, aiBusy);
  const impacts = impactSections(packet.change_impact);
  const effectiveReviews = Object.fromEntries((packet.impact_confirmations?.effective || []).map((item) => [item.relationship_id, item]));
  const actions = packet.change_impact?.suggested_actions?.actions || [];
  const resolutions = packet.impact_resolutions?.resolutions || [];
  return (
    <div className="mb-4 overflow-hidden rounded-xl border border-blue-200 bg-blue-50/40">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-blue-100 p-3">
        <div>
          <div className="text-sm font-semibold text-gray-900">Reviewer Change Brief</div>
          <div className="text-xs text-gray-600">{packet.document.document_id} · {brief.comparison.from_version} → {brief.comparison.to_version} · deterministic evidence first</div>
        </div>
        <button onClick={onRefresh} className="inline-flex items-center gap-1 rounded border border-blue-200 bg-white px-2 py-1 text-xs text-blue-700"><RefreshCw size={12} /> Refresh evidence</button>
      </div>
      <div className="grid gap-3 p-3 lg:grid-cols-2">
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Changed</div>
          {brief.changed.length ? <ul className="mt-2 space-y-1 text-xs">{brief.changed.slice(0, 10).map((e) => <li key={e.evidence_id}><a className="font-mono text-blue-700" href={`#review-evidence-${e.evidence_id}`}>{e.evidence_id}</a> {e.summary}</li>)}</ul> : <div className="mt-2 text-xs text-gray-500">No deterministic changed items recorded.</div>}
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">Your responsibility</div>
          <div className="mt-2 text-xs font-medium">{brief.responsibility.role} · {brief.responsibility.purpose}</div>
          <div className="mt-1 text-xs">{brief.responsibility.instruction_label || "Decision scope"}: {(brief.responsibility.confirms || []).join("; ") || "—"}</div>
          <div className="mt-1 text-xs text-gray-600">Outside scope: {(brief.responsibility.excludes || []).join("; ") || "—"}</div>
          {brief.responsibility.authority_limit && <div className="mt-1 text-xs font-medium text-blue-700">{brief.responsibility.authority_limit}</div>}
        </div>
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-amber-800">Needs attention / still open</div>
          {[...brief.needs_attention, ...brief.still_open].length ? <ul className="mt-2 space-y-1 text-xs">{[...brief.needs_attention, ...brief.still_open].slice(0, 10).map((e) => <li key={e.evidence_id}><a className="font-mono text-blue-700" href={`#review-evidence-${e.evidence_id}`}>{e.evidence_id}</a> {e.summary}</li>)}</ul> : <div className="mt-2 text-xs text-gray-500">No recorded attention or open items.</div>}
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-3 text-xs text-gray-600">
          <div className="font-semibold uppercase tracking-wide text-gray-500">Evidence identity</div>
          <div className="mt-2">Packet {packet.contract_version} · {packet.evidence_items.length} items</div>
          <div className="break-all font-mono text-[10px]">{packet.evidence_packet_hash}</div>
          {brief.limitations.map((x) => <div key={x} className="mt-1 text-amber-700">{x}</div>)}
        </div>
      </div>

      <div className="border-t border-cyan-200 bg-cyan-50/60 p-3">
        <div className="text-sm font-semibold text-cyan-950">Change Impact</div>
        <div className="mt-0.5 text-xs text-cyan-800">One-hop, evidence-backed relationships only. Impact recommends review; it does not trigger action or invalidate acceptance.</div>
        <div className="mt-3 grid gap-3 lg:grid-cols-3">
          <div className="rounded-lg border border-emerald-200 bg-white p-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-emerald-800">Known</div>
            {impacts.known.length ? <ul className="mt-2 space-y-2 text-xs">{impacts.known.map((item) => <li key={item.impact_id}>
              <div className="font-medium">{item.impact_type.replaceAll("_", " ")}</div>
              <div className="text-gray-600">{item.rationale}</div>
              <div className="mt-1 text-[10px] text-gray-400">{item.relationship_class} · {item.rule?.rule_id} v{item.rule?.rule_version}</div>
            </li>)}</ul> : <div className="mt-2 text-xs text-gray-500">No deterministic impact candidate is proven.</div>}
          </div>
          <div className="rounded-lg border border-violet-200 bg-white p-3">
            <div className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-violet-800">Possible <Badge tone="violet">AI Suggested</Badge></div>
            {impacts.suggested.length ? <ul className="mt-2 space-y-2 text-xs">{impacts.suggested.map((item) => {
              const rel = item.relationship || item;
              const review = effectiveReviews[rel.relationship_id];
              return <li key={item.impact_id || rel.relationship_id}>
                <div>{item.rationale || rel.advisory?.reason}</div>
                {review ? <div className="mt-1"><Badge tone={review.human_review_status === "CONFIRMED" ? "emerald" : review.human_review_status === "REJECTED" ? "rose" : "amber"}>{review.human_review_status}</Badge> by {review.actor_name}</div> : <ImpactReviewButtons disabled={impactBusy} onDecision={(decision) => onReviewImpact(rel, decision, item.impact_id, rel.advisory?.evidence_ids || [])} />}
              </li>;
            })}</ul> : <div className="mt-2 text-xs text-gray-500">No AI relationships requested. Suggestions never become authority automatically.</div>}
          </div>
          <div className="rounded-lg border border-gray-200 bg-white p-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-gray-600">Unknown</div>
            {impacts.unknown.length ? <ul className="mt-2 space-y-2 text-xs text-gray-600">{impacts.unknown.map((item) => {
              const review = effectiveReviews[item.relationship?.relationship_id];
              return <li key={item.domain}><span className="font-medium">{item.domain}:</span> {item.rationale}
                {review ? <div className="mt-1"><Badge tone={review.human_review_status === "CONFIRMED" ? "emerald" : review.human_review_status === "REJECTED" ? "rose" : "amber"}>{review.human_review_status}</Badge> by {review.actor_name}{review.stale ? " · evidence changed" : ""}</div> : <ImpactReviewButtons disabled={impactBusy} onDecision={(decision) => onReviewImpact(item.relationship, decision)} />}
              </li>;
            })}</ul> : <div className="mt-2 text-xs text-gray-500">No unresolved domains recorded.</div>}
          </div>
        </div>
        <details className="mt-3 rounded-lg border border-cyan-200 bg-white p-2 text-xs">
          <summary className="cursor-pointer font-semibold text-cyan-900">Relationship provenance ({packet.change_impact?.relationships?.length || 0})</summary>
          <div className="mt-2 space-y-2">{(packet.change_impact?.relationships || []).map((rel) => <div key={rel.relationship_id} className="border-t border-gray-100 pt-2">
            <div><span className="font-mono text-blue-700">{rel.relationship_id}</span> · {rel.source_type} {rel.relationship_type} {rel.target_type} · <Badge tone={rel.relationship_class === "EXPLICIT" ? "emerald" : "blue"}>{rel.relationship_class}</Badge></div>
            <div className="mt-1 break-all text-gray-500">{JSON.stringify(rel.provenance)}</div>
          </div>)}</div>
        </details>
        <div className="mt-3 rounded-lg border border-cyan-200 bg-white p-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-cyan-900">Suggested Next Actions</div>
          {actions.length ? <div className="mt-2 flex flex-wrap gap-2">{actions.map((action) => action.route
            ? <a key={action.action_id} href={action.route} className="rounded border border-cyan-200 px-2 py-1 text-xs text-cyan-800">{action.label} · {action.execution_mode.replaceAll("_", " ")}</a>
            : <span key={action.action_id} className="rounded border border-gray-200 px-2 py-1 text-xs text-gray-600">{action.label} · {action.execution_mode.replaceAll("_", " ")}</span>)}</div>
            : <div className="mt-2 text-xs text-gray-500">No action recommendation is supported.</div>}
          <div className="mt-2 text-[10px] text-gray-500">Recommendations do not execute owner-service writes.</div>
        </div>
        {(packet.impact_confirmations?.history || []).length > 0 && <details className="mt-3 rounded-lg border border-cyan-200 bg-white p-2 text-xs">
          <summary className="cursor-pointer font-semibold text-cyan-900">Relationship review history ({packet.impact_confirmations.history.length})</summary>
          <div className="mt-2 space-y-2">{packet.impact_confirmations.history.map((review) => <div key={review.confirmation_id} className="border-t border-gray-100 pt-2">
            <div><Badge tone={review.human_review_status === "CONFIRMED" ? "emerald" : review.human_review_status === "REJECTED" ? "rose" : "amber"}>{review.human_review_status}</Badge> {review.actor_name} · {formatDateTime(review.reviewed_at)}</div>
            <div className="text-gray-500">Origin {review.relationship_class_at_review} · evidence {(review.evidence_hash || "").slice(0, 12)} · {review.reason || "No reason supplied"}</div>
          </div>)}</div>
        </details>}
        {(packet.impact_confirmations?.effective || []).some(routedActionForReview) && <div className="mt-3 rounded-lg border border-indigo-200 bg-indigo-50 p-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-indigo-900">Controlled Owner Actions</div>
          <div className="mt-1 text-xs text-indigo-800">Relationship confirmation is complete. Execution is a separate explicit human decision.</div>
          <div className="mt-2 flex flex-wrap gap-2">{packet.impact_confirmations.effective.filter(routedActionForReview).map((review) => <button key={review.confirmation_id} disabled={actionBusy} onClick={() => onPreviewAction(review)} className="rounded bg-indigo-700 px-3 py-1.5 text-xs text-white disabled:opacity-50">Review {routedActionForReview(review) === "ROUTE_PM_DELIVERY_HANDOFF" ? "PM Handoff" : "QA Handoff"}</button>)}</div>
        </div>}
        {resolutions.length > 0 && <div className="mt-3 rounded-lg border border-sky-200 bg-white p-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-sky-900">Impact Resolution</div>
          <div className="mt-2 space-y-3">{resolutions.map((resolution) => <div key={resolution.resolution_id} className="border-t border-sky-100 pt-2 text-xs">
            <div className="flex flex-wrap items-center gap-2"><Badge tone={resolution.resolution_state === "RESOLVED" ? "emerald" : resolution.resolution_state === "BLOCKED" ? "rose" : resolution.resolution_state === "UNKNOWN" || resolution.resolution_state === "RECHECK_REQUIRED" ? "amber" : "blue"}>{resolution.resolution_state.replaceAll("_", " ")}</Badge><span>{resolution.resolution_reason}</span></div>
            <div className="mt-1 text-[10px] text-gray-500">Rule {resolution.evaluation_rule_id} v{resolution.evaluation_rule_version} · evaluated {formatDateTime(resolution.evaluated_at)}{resolution.owner_result_ref?.service ? ` · waiting on ${resolution.owner_result_ref.service}` : ""}</div>
            <button disabled={actionBusy} onClick={() => onRecheckResolution(resolution.confirmation_id)} className="mt-2 inline-flex items-center gap-1 rounded border border-sky-200 px-2 py-1 text-sky-800 disabled:opacity-50"><RefreshCw size={11} /> Recheck authoritative truth</button>
            {resolution.history?.length > 0 && <details className="mt-2"><summary className="cursor-pointer text-sky-800">Resolution timeline ({resolution.history.length})</summary><div className="mt-1 space-y-1">{resolution.history.map((event, index) => <div key={`${event.timestamp}-${index}`}>{formatDateTime(event.timestamp)} · {event.from_state || "NEW"} → {event.state} · {event.reason}</div>)}</div></details>}
          </div>)}</div>
          <div className="mt-2 text-[10px] text-gray-500">Owner action success is not resolution. Customer acceptance is separate.</div>
        </div>}
        {actionPreview && <div className="mt-3 rounded-lg border-2 border-indigo-300 bg-white p-3 text-xs">
          <div className="font-semibold text-indigo-950">Action Preview — {actionPreview.label}</div>
          <div className="mt-2">Target: {actionPreview.target_service} / {actionPreview.target_entity_id || "binding unavailable"}</div>
          <div className="mt-1">What will change: {actionPreview.what_will_change}</div>
          <div className="mt-1 text-gray-600">{actionPreview.what_will_not_change}</div>
          <div className="mt-1">Evidence: {(actionPreview.evidence_refs || []).join(" · ")}</div>
          {actionPreview.required_input?.length > 0 && <div className="mt-2 text-amber-700">Required input: {actionPreview.required_input.join(", ")}</div>}
          <div className="mt-3 flex gap-2"><button onClick={onCancelAction} className="rounded border border-gray-300 px-3 py-1.5">Cancel</button><button disabled={!actionPreview.executable || actionBusy} onClick={onExecuteAction} className="rounded bg-indigo-700 px-3 py-1.5 text-white disabled:opacity-50">Execute Human-Approved Action</button></div>
        </div>}
        {actionResult && <div className={`mt-3 rounded-lg border p-3 text-xs ${actionResult.status === "SUCCEEDED" ? "border-emerald-300 bg-emerald-50" : "border-amber-300 bg-amber-50"}`}>
          <div className="font-semibold">Action {actionResult.status === "SUCCEEDED" ? "completed by owner service" : "not completed"}</div>
          {actionResult.result_ref && <div className="mt-1">{actionResult.result_ref.service} result {actionResult.result_ref.entity_id} · {actionResult.result_ref.status}</div>}
          {actionResult.failure_category && <div className="mt-1">{actionResult.failure_category}: {actionResult.failure_detail}</div>}
          <div className="mt-1 text-gray-600">Impact is not automatically resolved.</div>
          {impactResolutionFromActionResult(actionResult) && <div className="mt-2 font-medium">Resolution: {impactResolutionFromActionResult(actionResult).resolution_state.replaceAll("_", " ")} — {impactResolutionFromActionResult(actionResult).resolution_reason}</div>}
        </div>}
      </div>

      <div className="border-t border-violet-200 bg-violet-50 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="inline-flex items-center gap-1 text-sm font-semibold text-violet-900"><Sparkles size={14} /> AI Reviewer Assistant <Badge tone="violet">Advisory</Badge> {aiStatus?.status && <Badge tone={aiStatus.status === "AI_AVAILABLE" ? "emerald" : "gray"}>{aiStatus.status.replaceAll("AI_", "").replaceAll("_", " ")}</Badge>}</div>
            <div className="text-xs text-violet-700">Grounded in the review evidence shown below. You make the decision.</div>
            {aiStatus?.message && <div className="mt-0.5 text-[10px] text-violet-600">{aiStatus.message}</div>}
          </div>
          <div className="flex gap-2">
            {!showAi && <button onClick={onShowAi} className="rounded bg-violet-700 px-3 py-1.5 text-xs text-white">Show AI guidance</button>}
            {showAi && ai?.status === "AVAILABLE" && <button onClick={onRefreshAi} disabled={aiBusy} className="rounded border border-violet-300 bg-white px-3 py-1.5 text-xs text-violet-800">Refresh AI guidance</button>}
            {showAi && aiFailed && <button onClick={onRefreshAi} disabled={aiBusy} className="rounded border border-violet-300 bg-white px-3 py-1.5 text-xs text-violet-800">Retry AI guidance</button>}
            {showAi && <button onClick={onHideAi} className="rounded border border-violet-300 px-3 py-1.5 text-xs text-violet-800">Hide</button>}
          </div>
        </div>
        {showAi && aiBusy && <div className="mt-3 text-xs text-violet-700">Generating cited guidance… The deterministic brief remains available.</div>}
        {showAi && !aiBusy && ai && ai.status !== "AVAILABLE" && <div className="mt-3 rounded border border-amber-200 bg-white p-2 text-xs text-amber-800">{ai.message || "AI guidance is unavailable."}</div>}
        {showAi && !aiBusy && ai?.status === "AVAILABLE" && !aiCurrent && <div className="mt-3 rounded border border-amber-200 bg-white p-2 text-xs text-amber-800">AI guidance is stale for the current evidence. Refresh it before use.</div>}
        {showAi && !aiBusy && ai?.status === "AVAILABLE" && aiCurrent && (
          <div className="mt-3 space-y-3">
            <div className="text-xs text-gray-700">{ai.summary}</div>
            {aiSections.map(([label, key]) => ai[key]?.length > 0 && <div key={key} className="rounded-lg border border-violet-100 bg-white p-3">
              <div className="text-xs font-semibold text-violet-900">{label}</div>
              <ul className="mt-2 space-y-2 text-xs">{ai[key].map((item, idx) => <li key={`${key}-${idx}`}>
                {item.title && <div className="font-medium">{item.title}</div>}
                <div>{item.explanation || item.statement}</div>
                <div className="mt-1 flex flex-wrap gap-1">{validCitations(packet, item.evidence_ids).map((id) => <a key={id} href={`#review-evidence-${id}`} className="rounded bg-blue-50 px-1.5 py-0.5 font-mono text-blue-700">{id}</a>)}</div>
              </li>)}</ul>
            </div>)}
            {ai.limitations?.map((x) => <div key={x} className="text-xs text-amber-700">{x}</div>)}
          </div>
        )}
      </div>

      <details className="border-t border-blue-100 bg-white p-3">
        <summary className="cursor-pointer text-xs font-semibold text-blue-800">Inspect deterministic evidence ({packet.evidence_items.length})</summary>
        <div className="mt-2 grid gap-2">{packet.evidence_items.map((item) => <EvidenceItem key={item.evidence_id} item={byId[item.evidence_id]} />)}</div>
      </details>
    </div>
  );
}

// ── auxiliary tab components ────────────────────────────────────────────────
function SignoffRegister({ projectId, onExport }) {
  const [rows, setRows] = useState(null);
  useEffect(() => { humanApi.signoffRegister(projectId).then(setRows).catch(() => setRows([])); }, [projectId]);
  if (rows === null) return <Loading />;
  return (
    <Card>
      <CardHeader title="Acceptance & Sign-off Register"
        right={<button onClick={onExport} className="inline-flex items-center gap-1 rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs hover:bg-gray-50"><Download size={13} /> Export evidence</button>} />
      {!rows.length ? <div className="p-4 text-sm text-gray-500">No sign-offs recorded yet.</div> : (
        <Table head={["Sign-off ID", "Document", "Version", "Decision", "Signer", "Role", "Signed At", "Hash"]}>
          {rows.map((s) => (
            <Tr key={s.signoff_id}>
              <Td><span className="text-xs">{s.signoff_id}</span></Td>
              <Td><div className="font-medium">{s.document_id}</div><div className="text-xs text-gray-400">{s.human_code}</div></Td>
              <Td>{s.document_version}</Td>
              <Td><Badge tone={s.decision.includes("REJECT") ? "rose" : "emerald"}>{s.decision}</Badge></Td>
              <Td>{s.signer_name}</Td>
              <Td>{s.signer_role || "—"}</Td>
              <Td>{formatDateTime(s.signed_at)}</Td>
              <Td><span className="text-xs">{(s.document_hash || "").slice(0, 12)}</span></Td>
            </Tr>
          ))}
        </Table>
      )}
    </Card>
  );
}

function MySignoffs({ projectId }) {
  const [rows, setRows] = useState(null);
  useEffect(() => { humanApi.mySignoffs(projectId).then(setRows).catch(() => setRows([])); }, [projectId]);
  if (rows === null) return <Loading />;
  if (!rows.length) return <div className="p-4 text-sm text-gray-500">You have not signed anything on this project.</div>;
  return (
    <Table head={["Document", "Version", "Decision", "Signed At", "Deliverable"]}>
      {rows.map((s) => (
        <Tr key={s.signoff_id}>
          <Td>{s.document_id}</Td>
          <Td>{s.document_version}</Td>
          <Td><Badge tone={s.decision.includes("REJECT") ? "rose" : "emerald"}>{s.decision}</Badge></Td>
          <Td>{formatDateTime(s.signed_at)}</Td>
          <Td>{s.human_code}</Td>
        </Tr>
      ))}
    </Table>
  );
}

function AuditTrail({ projectId }) {
  const [rows, setRows] = useState(null);
  useEffect(() => { humanApi.auditTrail(projectId).then(setRows).catch(() => setRows([])); }, [projectId]);
  if (rows === null) return <Loading />;
  if (!rows.length) return <div className="p-4 text-sm text-gray-500">No audit events yet.</div>;
  return (
    <Table head={["Timestamp", "Action", "Object", "Actor", "Reason"]}>
      {rows.map((a) => (
        <Tr key={a.id}>
          <Td>{formatDateTime(a.timestamp)}</Td>
          <Td><Badge tone="blue">{a.action}</Badge></Td>
          <Td><div className="text-xs">{a.object_type}</div><div className="text-xs text-gray-400">{a.object_id}</div></Td>
          <Td>{a.actor_name}</Td>
          <Td><div className="max-w-xs text-xs">{a.reason}</div></Td>
        </Tr>
      ))}
    </Table>
  );
}
