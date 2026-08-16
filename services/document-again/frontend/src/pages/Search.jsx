import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import { useWorkspace } from "../App.jsx";
import { Card, Empty, StatusBadge, inputClass } from "../components/ui.jsx";

/*
 * Project-wide semantic search. Favours semantic objects over file names
 * and lets you navigate straight to the object.
 */
const KIND_ROUTES = {
  REQUIREMENT: "/requirements",
  DB_SCHEMA: "/design/database",
  DB_TABLE: "/design/database",
  DB_FIELD: "/design/database",
  DB_RELATION: "/design/database",
  DOCUMENT_SECTION: "/design/dr",
  API_ENDPOINT: "/design/apis",
  PROCESS_FLOW: "/design/flows",
  PROCESS_STEP: "/design/flows",
  ARCHITECTURE_NODE: "/design/architecture",
  SCREEN: "/design/architecture",
  CHANGE_REQUEST: "/change-requests",
};

export function Search() {
  const { project, setFocus } = useWorkspace();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [searched, setSearched] = useState(false);

  useEffect(() => {
    if (!project || !q.trim()) { setResults([]); setSearched(false); return; }
    const t = setTimeout(() => {
      api.get(`/projects/${project.id}/search?q=${encodeURIComponent(q.trim())}`).then((rows) => {
        setResults(rows);
        setSearched(true);
      }).catch(() => {});
    }, 250);
    return () => clearTimeout(t);
  }, [project?.id, q]);

  function open(result) {
    setFocus(result.semantic_id, result.title || result.semantic_id);
    if (result.kind === "annotation") {
      navigate("/comments");
    } else if (result.kind === "change_request") {
      navigate("/change-requests");
    } else {
      navigate(KIND_ROUTES[result.object_type] || "/requirements");
    }
  }

  return (
    <div className="space-y-4">
      <Card title="Semantic search — objects over file names">
        <input
          className={inputClass}
          placeholder="Search: customer_id, REQ-022, approval_history…"
          value={q}
          autoFocus
          onChange={(e) => setQ(e.target.value)}
        />
        <div className="mt-4 space-y-1">
          {!q.trim() && <Empty>Type to search semantic objects, requirements, comments and change requests.</Empty>}
          {searched && results.length === 0 && <Empty>No matches for “{q}”.</Empty>}
          {results.map((r, i) => (
            <button
              key={i}
              onClick={() => open(r)}
              className="flex w-full items-center gap-3 rounded border border-line bg-surface-2 px-3 py-2 text-left hover:border-brand-500"
            >
              <span className="w-32 shrink-0 text-[11px] uppercase tracking-wider text-slate-500">{r.kind.replaceAll("_", " ")}</span>
              <span className="w-40 shrink-0 font-mono text-[12px] text-brand-300">{r.semantic_id}</span>
              <span className="min-w-0 flex-1 truncate text-[13px] text-slate-300">{r.title}</span>
              {r.status && <StatusBadge status={r.status} />}
            </button>
          ))}
        </div>
      </Card>
    </div>
  );
}