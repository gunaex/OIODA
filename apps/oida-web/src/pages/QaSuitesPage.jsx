import { useEffect, useState } from "react";
import { qaApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, StatusBadge, Loading, Empty, SignInPrompt, Table, Tr, Td } from "../components/ui";

export default function QaSuitesPage() {
  const { qa, qaAuthed } = useProjectCtx();
  const slug = qa && qa.length ? qa[0].slug : null;
  const [suites, setSuites] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const [revisions, setRevisions] = useState(null);
  const [cases, setCases] = useState(null);
  const [caseRev, setCaseRev] = useState(null);
  const [form, setForm] = useState({ name: "", suite_type: "OTHER" });
  const [caseForm, setCaseForm] = useState({ checkpoint_code: "", title: "", action_md: "", expected_result_md: "" });
  const [revForm, setRevForm] = useState({ revision_label: "", change_summary: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  function load() { if (slug) qaApi.suites(slug).then(setSuites).catch(() => setSuites([])); }
  useEffect(load, [slug]);

  async function createSuite() {
    if (!form.name.trim()) return;
    try { await qaApi.createSuite(slug, { name: form.name, suite_type: form.suite_type }); setForm({ name: "", suite_type: "OTHER" }); load(); }
    catch (e) { setError(e.message || String(e)); }
  }

  async function openRevisions(suiteId) {
    setExpanded(suiteId); setCases(null); setCaseRev(null);
    qaApi.revisions(slug, suiteId).then(setRevisions).catch(() => setRevisions([]));
  }

  async function openCases(revId) {
    setCaseRev(revId);
    qaApi.cases(slug, revId).then(setCases).catch(() => setCases([]));
  }

  async function createCase() {
    if (!caseForm.checkpoint_code.trim() || !caseForm.title.trim()) return;
    try {
      await qaApi.createCase(slug, caseRev, {
        checkpoint_code: caseForm.checkpoint_code, title: caseForm.title,
        action_md: caseForm.action_md, expected_result_md: caseForm.expected_result_md,
      });
      setCaseForm({ checkpoint_code: "", title: "", action_md: "", expected_result_md: "" });
      openCases(caseRev);
    } catch (e) { setError(e.message || String(e)); }
  }

  async function createRevision() {
    if (!revForm.revision_label.trim()) return;
    setBusy(true); setError(null);
    try {
      await qaApi.createRevision(slug, expanded, {
        revision_label: revForm.revision_label,
        change_summary: revForm.change_summary || null,
      });
      setRevForm({ revision_label: "", change_summary: "" });
      openRevisions(expanded);
    } catch (e) { setError(e.message || String(e)); }
    finally { setBusy(false); }
  }

  async function publishRevision(revId) {
    setBusy(true); setError(null);
    try {
      await qaApi.publishRevision(slug, expanded, revId);
      openRevisions(expanded);
    } catch (e) { setError(e.message || String(e)); }
    finally { setBusy(false); }
  }

  if (!qaAuthed) return <SignInPrompt service="QA Again" children="Sign in to manage QA suites and cases." />;
  if (!slug) return <Empty title="QA Again is not linked" />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold">Test Suites</h1>
        <p className="text-sm text-gray-500">Suites → revisions → test cases. Authority: QA Again.</p>
      </div>

      <Card className="px-4 py-3">
        <div className="flex gap-2 text-sm">
          <input className="input flex-1" placeholder="Suite name *" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <select className="input !w-40" value={form.suite_type} onChange={(e) => setForm({ ...form, suite_type: e.target.value })}>
            {["REGRESSION", "UAT", "SMOKE", "INTEGRATION", "OTHER"].map((t) => <option key={t}>{t}</option>)}
          </select>
          <button onClick={createSuite} disabled={!form.name.trim()} className="rounded-lg bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-700 disabled:opacity-50">Create Suite</button>
        </div>
        {error && <div className="mt-2 text-xs text-rose-600">{error}</div>}
      </Card>

      <Card>
        <CardHeader title={`Suites (${suites?.length ?? "…"})`} subtitle="Click Revisions to drill into test cases." />
        {!suites ? <Loading /> : suites.length === 0 ? <Empty title="No suites" /> : (
          <Table head={["Suite", "Type", "Status", ""]}>
            {suites.map((s) => (
              <Tr key={s.id}>
                <Td className="font-medium text-gray-800">{s.suite_code ? `${s.suite_code} — ` : ""}{s.name}</Td>
                <Td className="text-gray-600">{s.suite_type}</Td>
                <Td><StatusBadge status={s.status} /></Td>
                <Td className="text-right"><button onClick={() => openRevisions(s.id)} className="text-xs font-medium text-gray-900 hover:underline">Revisions</button></Td>
              </Tr>
            ))}
          </Table>
        )}
      </Card>

      {expanded && (
        <Card>
          <CardHeader title="Revisions" />
          <div className="flex gap-2 border-b border-gray-100 px-4 py-2 text-sm">
            <input className="input flex-1" placeholder="Revision label *" value={revForm.revision_label} onChange={(e) => setRevForm({ ...revForm, revision_label: e.target.value })} />
            <input className="input flex-1" placeholder="Change summary" value={revForm.change_summary} onChange={(e) => setRevForm({ ...revForm, change_summary: e.target.value })} />
            <button onClick={createRevision} disabled={busy || !revForm.revision_label.trim()} className="rounded-lg bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-700 disabled:opacity-50">Add Revision</button>
          </div>
          {!revisions ? <Loading /> : revisions.length === 0 ? <div className="px-4 py-3 text-sm text-gray-400">No revisions.</div> : (
            <Table head={["Revision", "Status", "", ""]}>
              {revisions.map((r) => (
                <Tr key={r.id}>
                  <Td className="font-medium text-gray-800">{r.revision_label}</Td>
                  <Td><StatusBadge status={r.status} /></Td>
                  <Td className="text-right"><button onClick={() => openCases(r.id)} className="text-xs font-medium text-gray-900 hover:underline">Cases</button></Td>
                  <Td className="text-right">
                    {r.status === "DRAFT" && (
                      <button onClick={() => publishRevision(r.id)} disabled={busy} className="rounded bg-emerald-600 px-2 py-1 text-[10px] font-medium text-white hover:bg-emerald-500 disabled:opacity-50">Publish</button>
                    )}
                  </Td>
                </Tr>
              ))}
            </Table>
          )}
        </Card>
      )}

      {caseRev && (
        <Card>
          <CardHeader title={`Test cases (${cases?.length ?? "…"})`} />
          <div className="border-b border-gray-100 px-4 py-2">
            <div className="grid gap-1.5 text-sm md:grid-cols-2">
              <input className="input" placeholder="Checkpoint code *" value={caseForm.checkpoint_code} onChange={(e) => setCaseForm({ ...caseForm, checkpoint_code: e.target.value })} />
              <input className="input" placeholder="Title *" value={caseForm.title} onChange={(e) => setCaseForm({ ...caseForm, title: e.target.value })} />
              <input className="input" placeholder="Actions" value={caseForm.action_md} onChange={(e) => setCaseForm({ ...caseForm, action_md: e.target.value })} />
              <input className="input" placeholder="Expected result" value={caseForm.expected_result_md} onChange={(e) => setCaseForm({ ...caseForm, expected_result_md: e.target.value })} />
            </div>
            <button onClick={createCase} disabled={!caseForm.checkpoint_code.trim() || !caseForm.title.trim()} className="mt-2 rounded-lg bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-700 disabled:opacity-50">Add Case</button>
          </div>
          {!cases ? <Loading /> : cases.length === 0 ? <div className="px-4 py-3 text-sm text-gray-400">No cases in this revision.</div> : (
            <ul className="divide-y divide-gray-100">
              {cases.map((c) => (
                <li key={c.id} className="px-4 py-2 text-sm">
                  <span className="font-medium text-gray-800">{c.checkpoint_code}</span>
                  <span className="ml-2 text-gray-700">{c.title}</span>
                  <span className="ml-2 text-xs text-gray-400">{c.priority || "—"} · {c.category || "—"}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </div>
  );
}
