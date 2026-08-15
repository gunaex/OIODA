import React, { useCallback, useEffect, useState } from "react";
import { api } from "../api/client.js";
import { useWorkspace } from "../App.jsx";
import { Button, Card, Empty, ErrorNote, Field, StatusBadge, inputClass } from "../components/ui.jsx";

/*
 * UR / DR artifact workspace: revision list with the full lifecycle —
 * edit draft → submit for review → confirm (immutable) → clone as new
 * revision. Confirming and editing rules come from the backend; the
 * 409 error text is shown verbatim so invariants are visible.
 */
export function Artifacts({ type }) {
  const { project, setFocus } = useWorkspace();
  const [artifacts, setArtifacts] = useState([]);
  const [selected, setSelected] = useState(null); // artifact with revisions
  const [error, setError] = useState(null);
  const [title, setTitle] = useState("");

  const load = useCallback(() => {
    if (!project) return;
    api.get(`/projects/${project.id}/artifacts`)
      .then((rows) => setArtifacts(rows.filter((a) => a.type === type)))
      .catch(setError);
  }, [project?.id, type]);

  useEffect(load, [load]);

  function open(a) {
    api.get(`/artifacts/${a.id}`).then((full) => {
      setSelected(full);
      const current = full.revisions.find((r) => r.id === full.current_draft_revision_id) || full.revisions.at(-1);
      setFocus(`sec_${current.id}`, `${type} r${current.revision_number}`);
    });
  }

  async function createArtifact(e) {
    e.preventDefault();
    setError(null);
    try {
      const created = await api.post("/artifacts", {
        project_id: project.id, type, title,
        snapshot: { sections: [{ id: "overview", note: "draft" }] },
      });
      setTitle("");
      load();
      open(created);
    } catch (err) {
      setError(err);
    }
  }

  async function action(path, body) {
    setError(null);
    try {
      await api.post(path, body);
      if (selected) open(selected);
      load();
    } catch (err) {
      setError(err);
    }
  }

  async function clone(rev) {
    setError(null);
    try {
      await api.post(`/artifacts/${selected.id}/revisions`, { based_on_revision_id: rev.id });
      open(selected);
      load();
    } catch (err) {
      setError(err);
    }
  }

  async function editSnapshot(rev) {
    setError(null);
    const json = prompt("New snapshot JSON", JSON.stringify(rev.snapshot || {}, null, 2));
    if (json === null) return;
    try {
      const snapshot = JSON.parse(json);
      await api.put(`/revisions/${rev.id}/snapshot`, { snapshot });
      open(selected);
    } catch (err) {
      setError(err instanceof SyntaxError ? new Error("Invalid JSON") : err);
    }
  }

  return (
    <div className="grid grid-cols-[300px_1fr] gap-4">
      <Card title={`${type} artifacts`}>
        {artifacts.length === 0 && <Empty>None yet.</Empty>}
        <ul className="space-y-1">
          {artifacts.map((a) => (
            <li key={a.id}>
              <button
                onClick={() => open(a)}
                className={`w-full rounded px-2 py-1.5 text-left text-[13px] ${
                  selected?.id === a.id ? "bg-brand-600/20 text-brand-100" : "text-slate-300 hover:bg-surface-2"
                }`}
              >
                {a.title}
              </button>
            </li>
          ))}
        </ul>
        <form onSubmit={createArtifact} className="mt-4 space-y-2 border-t border-line pt-3">
          <Field label={`New ${type} title`}>
            <input className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} required />
          </Field>
          <Button variant="primary" disabled={!title}>Create {type}</Button>
        </form>
      </Card>

      <div className="space-y-4">
        <ErrorNote error={error} />
        {!selected && <Card title="Revisions"><Empty>Select an artifact to see its revision history.</Empty></Card>}
        {selected && (
          <Card
            title={`${selected.title} — revisions`}
            actions={<span className="text-[11px] text-slate-500">{selected.id}</span>}
          >
            <table className="w-full text-[13px]">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wider text-slate-500">
                  <th className="pb-2">Rev</th><th className="pb-2">Status</th><th className="pb-2">Based on</th><th className="pb-2">Created</th><th className="pb-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {selected.revisions.map((r) => (
                  <tr key={r.id} className="border-t border-line/60 align-middle">
                    <td className="py-2 font-mono text-brand-300">r{r.revision_number}</td>
                    <td className="py-2"><StatusBadge status={r.status} /></td>
                    <td className="py-2 text-slate-500">{r.based_on_revision_id ? "…" + r.based_on_revision_id.slice(-6) : "—"}</td>
                    <td className="py-2 text-slate-500">{r.confirmed_by ? `confirmed by ${r.confirmed_by}` : `by ${r.created_by}`}</td>
                    <td className="py-2">
                      <span className="flex flex-wrap gap-1.5">
                        {r.status === "DRAFT" && (
                          <>
                            <Button onClick={() => editSnapshot(r)}>Edit</Button>
                            <Button onClick={() => action(`/revisions/${r.id}/submit-for-review`)}>Submit for review</Button>
                          </>
                        )}
                        {r.status === "IN_REVIEW" && (
                          <Button variant="primary" onClick={() => action(`/revisions/${r.id}/confirm`, { comment: "Confirmed from workspace" })}>
                            Confirm
                          </Button>
                        )}
                        {(r.status === "CONFIRMED" || r.status === "SUPERSEDED") && (
                          <Button onClick={() => clone(r)}>Clone as new revision</Button>
                        )}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-[11px] text-slate-500">
              CONFIRMED revisions are immutable — the backend rejects edits with 409. Use “Clone as new revision” to evolve a confirmed artifact.
            </p>
          </Card>
        )}
      </div>
    </div>
  );
}
