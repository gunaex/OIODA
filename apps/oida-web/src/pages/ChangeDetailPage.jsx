import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { documentApi, accountApi } from "../api";
import { Card, CardHeader, StatusBadge, Badge, Loading, formatDateTime } from "../components/ui";

const LEVEL_TONE = { DIRECT: "red", INDIRECT: "amber", POTENTIAL: "violet" };

export default function ChangeDetailPage() {
  const { projectId, changeId } = useParams();
  const [change, setChange] = useState(null);
  const [impact, setImpact] = useState(null);
  const [regenerated, setRegenerated] = useState(null);
  const [confirmResult, setConfirmResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [pw, setPw] = useState("");
  const [pwEmail, setPwEmail] = useState("admin@local.again");
  const [mode, setMode] = useState("affected");

  async function loadImpact() {
    setBusy(true);
    setError(null);
    try {
      setImpact(await documentApi.changeImpact(changeId));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function regenerate() {
    setBusy(true);
    setError(null);
    try {
      setRegenerated(await documentApi.regenerateChange(changeId, mode));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      const reauth = await accountApi.reauth(pwEmail, pw);
      if (!reauth.confirmationToken) throw new Error("Re-authentication failed");
      setConfirmResult(await documentApi.confirmChange(changeId, reauth.confirmationToken));
      setPw("");
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    documentApi.getChange(changeId).then(setChange).catch((e) => setError(e.message));
  }, [changeId]);

  if (error && !change && !impact) {
    return <Card className="px-6 py-10 text-center text-sm text-rose-600">{error}</Card>;
  }
  if (!change) return <Loading />;

  return (
    <div className="space-y-5">
      <div>
        <Link to={`/projects/${projectId}/changes`} className="text-sm text-gray-500 hover:text-gray-800">← Changes</Link>
        <div className="mt-1 flex items-center gap-3">
          <h1 className="text-lg font-bold">{change.code}</h1>
          <StatusBadge status={change.status} />
        </div>
        <p className="text-sm text-gray-600">{change.draft_title || change.label}</p>
      </div>

      {error && <Card className="px-4 py-3 text-sm text-rose-600">{error}</Card>}

      <Card>
        <CardHeader title="Impact analysis" subtitle="Exact trace links — no human memory." right={<button onClick={loadImpact} className="text-xs font-medium text-gray-900 hover:underline" disabled={busy}>{impact ? "Refresh" : "Run Impact Analysis"}</button>} />
        <div className="px-4 py-3">
          {!impact ? (
            <p className="text-sm text-gray-500">Run impact analysis to see what this change affects.</p>
          ) : (
            <div className="space-y-4">
              <div className="flex gap-3 text-sm">
                <span className="font-medium text-gray-800">{impact.affected_count} affected</span>
                <span className="text-gray-500">{impact.unaffected_count} unaffected</span>
                <span className="text-gray-400">· downstream: {impact.cross_domain?.join(", ")}</span>
              </div>
              <ul className="space-y-2">
                {impact.affected.map((a, i) => (
                  <li key={i} className="flex items-start gap-2 rounded-lg border border-gray-100 px-3 py-2 text-sm">
                    <Badge tone={LEVEL_TONE[a.level] || "gray"}>{a.level}</Badge>
                    <span className="text-gray-700">{a.display_name}</span>
                    <span className="ml-auto shrink-0 text-xs text-gray-400">{a.object_type}</span>
                    <span className="shrink-0 text-xs italic text-gray-400">{a.reason}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </Card>

      <Card>
        <CardHeader title="Regeneration" subtitle="Default: affected objects only." />
        <div className="space-y-3 px-4 py-3">
          <div className="flex gap-4 text-sm">
            <label className="flex items-center gap-1.5">
              <input type="radio" checked={mode === "affected"} onChange={() => setMode("affected")} /> Affected objects only
            </label>
            <label className="flex items-center gap-1.5">
              <input type="radio" checked={mode === "full"} onChange={() => setMode("full")} /> Full project regeneration (elevated)
            </label>
          </div>
          <button onClick={regenerate} disabled={busy || !impact} className="rounded-lg border border-gray-300 bg-gray-100 px-3 py-1.5 text-sm font-medium text-gray-900 hover:bg-gray-200 disabled:opacity-50">
            Regenerate Drafts
          </button>
          {regenerated && (
            <div className="text-sm">
              <div className="font-medium text-gray-700">Generated drafts ({regenerated.generated?.length || 0}):</div>
              <ul className="mt-1 space-y-1 text-gray-600">
                {(regenerated.generated || []).map((g) => (
                  <li key={g.revision_id}>• {g.artifact_title} → v{g.revision_number}</li>
                ))}
                {(regenerated.needs_regeneration || []).map((n) => (
                  <li key={n.semantic_id} className="text-amber-600">• {n.display_name} — needs regeneration (no draft model)</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </Card>

      <Card>
        <CardHeader title="Review & Confirm" subtitle="Admin re-authentication required. Password is never stored." />
        <div className="space-y-3 px-4 py-3">
          <div className="grid max-w-sm gap-2 text-sm">
            <input value={pwEmail} onChange={(e) => setPwEmail(e.target.value)} className="rounded-lg border border-gray-300 px-3 py-2" placeholder="Admin email" />
            <input type="password" value={pw} onChange={(e) => setPw(e.target.value)} className="rounded-lg border border-gray-300 px-3 py-2" placeholder="Admin password" />
          </div>
          <button onClick={confirm} disabled={busy || !regenerated || !pw} className="rounded-lg border border-gray-300 bg-gray-100 px-4 py-2 text-sm font-medium text-gray-900 hover:bg-gray-200 disabled:opacity-50">
            {busy ? "Working…" : "Confirm New Baseline"}
          </button>
          {confirmResult && (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm">
              <div className="font-medium text-emerald-800">Baseline {confirmResult.baseline.name} created</div>
              <div className="text-emerald-700">Sync: PM {confirmResult.sync.pm.status}, QA {confirmResult.sync.qa.status}, Infra {confirmResult.sync.infra.status} — {confirmResult.overall}</div>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
