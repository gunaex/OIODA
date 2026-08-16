import { useEffect, useState } from "react";
import { documentApi } from "../api";
import { Card, CardHeader, Badge, Loading } from "../components/ui";

const STATUS_TONE = {
  AVAILABLE: "green", CONFIGURED: "blue", NOT_CONFIGURED: "gray",
  NOT_AVAILABLE: "gray", UNAVAILABLE: "red", AUTH_FAILED: "red",
  RATE_LIMITED: "amber", TIMEOUT: "amber", DISABLED: "gray", DEGRADED: "amber",
};

export default function AiProvidersPage() {
  const [providers, setProviders] = useState(null);
  const [testResult, setTestResult] = useState(null);
  const [models, setModels] = useState({});       // provider_id -> {models, source, error}
  const [loadingModels, setLoadingModels] = useState({});
  const [form, setForm] = useState({});           // provider_id -> {api_key, model, base_url}
  const [saving, setSaving] = useState({});
  const [saved, setSaved] = useState({});
  const [editingKey, setEditingKey] = useState({});  // provider_id -> true while the user is changing a saved key

  useEffect(() => {
    documentApi.aiProviders().then((ps) => {
      setProviders(ps);
      const f = {};
      for (const p of ps) {
        if (p.provider_id !== "codex") f[p.provider_id] = { api_key: "", model: p.model || "", base_url: p.endpoint || "" };
      }
      setForm(f);
    }).catch(() => setProviders([]));
  }, []);

  async function test(id) {
    try { setTestResult({ id, ...(await documentApi.aiProvidersTest(id)) }); }
    catch (e) { setTestResult({ id, test: "ERROR", reason: e.message }); }
  }

  async function loadModels(id) {
    setLoadingModels((s) => ({ ...s, [id]: true }));
    try {
      const result = await documentApi.aiProviderModels(id, form[id]?.api_key || "");
      setModels((m) => ({ ...m, [id]: result }));
    }
    catch (e) { setModels((m) => ({ ...m, [id]: { models: [], error: e.message } })); }
    finally { setLoadingModels((s) => ({ ...s, [id]: false })); }
  }

  async function save(id) {
    setSaving((s) => ({ ...s, [id]: true }));
    setSaved((s) => ({ ...s, [id]: null }));
    try {
      const body = { model: form[id].model || null, base_url: form[id].base_url || null };
      if (form[id].api_key) body.api_key = form[id].api_key;  // only send when changed
      await documentApi.updateAiProviderSettings(id, body);
      setSaved((s) => ({ ...s, [id]: "Saved" }));
      setEditingKey((s) => ({ ...s, [id]: false }));  // re-lock the key after save
      documentApi.aiProviders().then(setProviders);
    } catch (e) { setSaved((s) => ({ ...s, [id]: `Error: ${e.message}` })); }
    finally { setSaving((s) => ({ ...s, [id]: false })); }
  }

  if (!providers) return <Loading />;

  const enabledCount = providers.filter((p) => p.status === "AVAILABLE").length;

  return (
    <div className="mx-auto max-w-3xl space-y-5 px-6 py-10">
      <div>
        <h1 className="text-lg font-bold">AI Providers</h1>
        <p className="text-sm text-gray-500">
          Set each provider's API key and pick a model. Model lists are read live from the provider — nothing is hard-coded.
        </p>
      </div>

      <Card className="border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-700">
        Consultation mode: <span className="font-semibold">{enabledCount > 0 ? "LOCAL ONLY" : "AI NOT CONFIGURED"}</span>
        <span className="text-gray-400"> · external providers stay NOT_CONFIGURED until a key is saved.</span>
      </Card>

      <div className="space-y-3">
        {providers.map((p) => {
          if (p.provider_id === "codex") {
            return (
              <Card key={p.provider_id} className="px-4 py-3">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-semibold text-gray-900">{p.display_name}</div>
                    <div className="text-xs text-gray-500">{p.runtime}</div>
                  </div>
                  <Badge tone={STATUS_TONE[p.status] || "gray"}>{p.status}</Badge>
                </div>
                <div className="mt-1 text-xs text-gray-400">{p.note}</div>
              </Card>
            );
          }
          const f = form[p.provider_id] || { api_key: "", model: "", base_url: "" };
          const m = models[p.provider_id];
          return (
            <Card key={p.provider_id} className="px-4 py-3">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm font-semibold text-gray-900">{p.display_name}</div>
                  <div className="text-xs text-gray-500">{p.runtime}{p.endpoint ? ` · ${p.endpoint}` : ""}</div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={STATUS_TONE[p.status] || "gray"}>{p.status}</Badge>
                  {(p.status === "AVAILABLE" || p.status === "CONFIGURED") && (
                    <button onClick={() => test(p.provider_id)} className="rounded-lg border border-gray-300 px-2 py-1 text-xs text-gray-600 hover:bg-gray-50">Test</button>
                  )}
                </div>
              </div>

              <div className="mt-3 space-y-2 border-t border-gray-100 pt-3">
                <div>
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-gray-500">API key</label>
                    {p.configured && !editingKey[p.provider_id] && (
                      <button
                        onClick={() => setEditingKey((s) => ({ ...s, [p.provider_id]: true }))}
                        className="text-[11px] font-medium text-gray-500 underline hover:text-gray-800"
                      >
                        Change key
                      </button>
                    )}
                  </div>
                  {p.configured && !editingKey[p.provider_id] ? (
                    <div className="input mt-1 flex items-center justify-between bg-gray-100 text-gray-400">
                      <span>•••••••••••••••• (key saved)</span>
                      <span className="text-[10px] uppercase tracking-wide">Locked</span>
                    </div>
                  ) : (
                    <input
                      type="password"
                      autoFocus={p.configured}
                      className="input mt-1"
                      placeholder="Paste API key"
                      value={f.api_key}
                      onChange={(e) => setForm((s) => ({ ...s, [p.provider_id]: { ...f, api_key: e.target.value } }))}
                    />
                  )}
                </div>

                <div className="flex items-end gap-2">
                  <div className="flex-1">
                    <label className="text-xs font-medium text-gray-500">Model</label>
                    <select
                      className="input mt-1"
                      value={f.model}
                      onChange={(e) => setForm((s) => ({ ...s, [p.provider_id]: { ...f, model: e.target.value } }))}
                    >
                      {f.model && <option value={f.model}>{f.model}</option>}
                      {(m?.models || []).filter((x) => x !== f.model).map((x) => <option key={x} value={x}>{x}</option>)}
                    </select>
                  </div>
                  <button
                    onClick={() => loadModels(p.provider_id)}
                    disabled={loadingModels[p.provider_id]}
                    className="rounded-lg border border-gray-300 px-3 py-2 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                  >
                    {loadingModels[p.provider_id] ? "Loading…" : "Load models from source"}
                  </button>
                </div>
                {m && (
                  <div className="text-[11px] text-gray-400">
                    {m.models?.length != null ? `${m.models.length} models from ${m.source}` : ""}
                    {m.error ? <span className="text-rose-500"> · {m.error}</span> : ""}
                  </div>
                )}

                <div>
                  <label className="text-xs font-medium text-gray-500">Base URL</label>
                  <input
                    className="input mt-1"
                    value={f.base_url}
                    onChange={(e) => setForm((s) => ({ ...s, [p.provider_id]: { ...f, base_url: e.target.value } }))}
                  />
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => save(p.provider_id)}
                    disabled={saving[p.provider_id]}
                    className="rounded-lg bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-700 disabled:opacity-50"
                  >
                    {saving[p.provider_id] ? "Saving…" : "Save"}
                  </button>
                  {saved[p.provider_id] && (
                    <span className={`text-xs ${saved[p.provider_id].startsWith("Error") ? "text-rose-600" : "text-emerald-600"}`}>{saved[p.provider_id]}</span>
                  )}
                </div>
              </div>

              {testResult?.id === p.provider_id && (
                <div className="mt-1 text-xs text-gray-600">Test: {testResult.test}{testResult.reason ? ` — ${testResult.reason}` : ""}</div>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
