import { useEffect, useMemo, useState } from "react";
import { humanApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import {
  Card, CardHeader, StatCard, Table, Tr, Td, Badge, Loading, OidaError, formatDateTime,
} from "../components/ui";
import {
  Download, RefreshCw, Stamp,
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
  const tone = { READY: "emerald", PARTIAL: "amber", MISSING: "rose", NO_SOURCE: "gray" }[state] || "gray";
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
  const [signoffForm, setSignoffForm] = useState({ decision: "ACCEPT", comment: "", signer_role: "", exceptions: "" });

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
    try {
      const d = await humanApi.detail(project.id, code);
      setDetail(d);
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
        comment: signoffForm.comment || null,
        signer_role: signoffForm.signer_role || null,
        known_exceptions: exceptions,
      });
      setSignoffForm({ decision: "ACCEPT", comment: "", signer_role: "", exceptions: "" });
      await refreshDetail(); await load();
    } catch (e) { setError(e.message || String(e)); }
    finally { setBusy(false); }
  }

  async function download(kind, code) {
    const url = humanApi.exportUrl(project.id, kind, code);
    if (!url) return;
    const token = localStorage.getItem("oida_ecosystem_token");
    const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = url.split("/").pop() || "export";
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
          <div className="grid grid-cols-3 gap-3">
            <StatCard label="Need My Review" value={data.my_actions.review} tone="blue" />
            <StatCard label="Need My Approval" value={data.my_actions.approval} tone="amber" />
            <StatCard label="Need My Sign-off" value={data.my_actions.signoff} tone="rose" />
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <StatCard label="Ready to Generate" value={data.summary.ready_to_generate} tone="emerald" />
            <StatCard label="Needs Information" value={data.summary.needs_information} tone="amber" />
            <StatCard label="Generated" value={data.summary.generated} tone="blue" />
            <StatCard label="Not Due" value={data.summary.not_due} tone="gray" />
            <StatCard label="Stale" value={data.summary.stale} tone="rose" />
          </div>

          {/* critical gates */}
          {data.gates?.length > 0 && (
            <Card>
              <CardHeader title="Critical Sign-off Gates" subtitle="Explicit human acceptance at responsibility boundaries." />
              <div className="flex flex-wrap gap-2 p-4">
                {data.gates.map((g) => (
                  <span key={g.gate} className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-gray-50 px-2.5 py-1.5 text-xs">
                    <span className="font-medium">{g.name}</span>
                    <Badge tone={g.status === "SIGNED" ? "emerald" : g.status === "NOT_APPLICABLE" ? "gray" : "amber"}>
                      {g.status === "NOT_APPLICABLE" ? "N/A" : g.status}
                    </Badge>
                  </span>
                ))}
              </div>
            </Card>
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
                          <span className="text-gray-400">{s.ready} ready · {s.missing} missing · {s.no_source} no source</span>
                        </div>
                        <div className="mt-1 flex flex-wrap gap-1">
                          {s.standards.map((std) => (
                            <span key={std.name} className="inline-flex items-center gap-1 rounded bg-gray-50 px-1.5 py-0.5 text-[10px]">
                              <SectionState state={std.state} />
                              {std.name}
                              {std.state !== "READY" && (
                                <a href={`${base}/${SOURCE_ROUTE[std.authority] || "requirements"}`} onClick={(e) => e.stopPropagation()}
                                  className="text-blue-600 underline">open {std.owner_label}</a>
                              )}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
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
                          <div className="mb-2 text-xs text-gray-500">Already signed: {detail.signoffs.map((s) => `${s.decision} by ${s.signer_name} (v${s.document_version})`).join("; ")}</div>
                        )}
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
                            <input value={signoffForm.signer_role} onChange={(e) => setSignoffForm({ ...signoffForm, signer_role: e.target.value })}
                              placeholder="e.g. CUSTOMER_TECHNICAL_OWNER" className="w-full rounded-lg border border-gray-300 px-2 py-1.5" />
                          </div>
                          <div className="col-span-2">
                            <label className="mb-1 block font-medium text-gray-600">Comment</label>
                            <textarea value={signoffForm.comment} onChange={(e) => setSignoffForm({ ...signoffForm, comment: e.target.value })}
                              placeholder="TEST / INTERNAL ACCEPTANCE" rows={2} className="w-full rounded-lg border border-gray-300 px-2 py-1.5" />
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
