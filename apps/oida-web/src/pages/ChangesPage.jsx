import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { documentApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, StatusBadge, Badge, Loading, Table, Tr, Td, formatDateTime } from "../components/ui";
import NewChangeRequestModal from "../components/NewChangeRequestModal";

export default function ChangesPage() {
  const { project, baselines } = useProjectCtx();
  const navigate = useNavigate();
  const [changes, setChanges] = useState(null);
  const [crs, setCrs] = useState(null);
  const [showNewCr, setShowNewCr] = useState(false);

  function load() {
    if (!project) return;
    documentApi.listChanges(project.id).then(setChanges).catch(() => setChanges([]));
    documentApi.listChangeRequests(project.id).then(setCrs).catch(() => setCrs([]));
  }

  useEffect(load, [project?.id]);

  if (!project) return <Loading />;

  const pending = (changes || []).filter((c) => c.status !== "CONFIRMED" && c.status !== "CANCELLED");
  const sortedBaselines = [...(baselines || [])].sort((a, b) =>
    String(a.name).localeCompare(String(b.name), undefined, { numeric: true })
  );
  const current = sortedBaselines[sortedBaselines.length - 1];

  const confidenceTone = { HIGH: "green", MEDIUM: "blue", LOW: "amber", UNKNOWN: "gray" };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-bold">Changes</h1>
        <p className="text-sm text-gray-500">
          Pending changes, change requests, baselines and history. Historical truth survives.
        </p>
      </div>

      <Card>
        <CardHeader title="Pending requirement changes" subtitle="Draft edits that have not yet been confirmed into a new baseline." />
        {!changes ? (
          <Loading />
        ) : pending.length === 0 ? (
          <div className="px-4 py-6 text-sm text-gray-500">No pending requirement changes.</div>
        ) : (
          <Table head={["Requirement", "Draft", "Impact", "Status", ""]}>
            {pending.map((c) => (
              <Tr key={c.id}>
                <Td className="font-medium text-gray-800">{c.code}</Td>
                <Td className="text-gray-600">{c.draft_title || "—"}</Td>
                <Td className="text-gray-600">
                  {c.affected_count != null ? `${c.affected_count} affected · ${c.unaffected_count} unaffected` : "Not analyzed"}
                </Td>
                <Td><StatusBadge status={c.status} /></Td>
                <Td className="text-right">
                  <Link to={`/projects/${project.id}/changes/${c.id}`} className="font-medium text-gray-900 hover:underline">
                    Review →
                  </Link>
                </Td>
              </Tr>
            ))}
          </Table>
        )}
      </Card>

      <Card>
        <CardHeader
          title="Change Requests"
          subtitle="Draft-first. Unapproved CRs never alter the current baseline."
          right={
            <button onClick={() => setShowNewCr(true)} className="rounded-lg bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-700">
              + New Change Request
            </button>
          }
        />
        {!crs ? (
          <Loading />
        ) : crs.length === 0 ? (
          <div className="px-4 py-6 text-sm text-gray-500">No change requests.</div>
        ) : (
          <Table head={["Code", "Title / requested change", "Classification", "Status", "Confidence", "Review", "Effort", "Commercial", ""]}>
            {crs.map((cr) => (
              <Tr key={cr.id}>
                <Td className="font-semibold text-gray-900">{cr.code}</Td>
                <Td className="max-w-[260px]">
                  <div className="font-medium text-gray-800">{cr.title || "—"}</div>
                  <div className="truncate text-xs text-gray-500">{cr.requested_change}</div>
                </Td>
                <Td>{cr.classification ? <Badge tone="violet">{cr.classification}</Badge> : <span className="text-xs text-gray-400">—</span>}</Td>
                <Td><StatusBadge status={cr.status} /></Td>
                <Td>{cr.impact_confidence ? <Badge tone={confidenceTone[cr.impact_confidence] || "gray"}>{cr.impact_confidence}</Badge> : <span className="text-xs text-gray-400">—</span>}</Td>
                <Td><span className="text-xs text-gray-600">{String(cr.human_review || "NOT_REVIEWED").replaceAll("_", " ")}</span></Td>
                <Td><span className="text-xs text-gray-600">{cr.effort_status || "—"}</span></Td>
                <Td><span className="text-xs text-gray-600">{cr.commercial_status || "—"}</span></Td>
                <Td className="text-right">
                  <Link to={`/projects/${project.id}/changes/cr/${cr.id}`} className="font-medium text-gray-900 hover:underline">
                    Open →
                  </Link>
                </Td>
              </Tr>
            ))}
          </Table>
        )}
      </Card>

      <Card>
        <CardHeader title="Baselines" subtitle={`Current: ${current?.name || "—"}`} />
        <Table head={["Version", "Name", "Status"]}>
          {sortedBaselines.map((b) => (
            <Tr key={b.id}>
              <Td className="font-semibold text-gray-900">{baselineVersion(b.name)}</Td>
              <Td className="text-gray-700">{b.name}</Td>
              <Td>{b.id === current?.id ? <Badge tone="green">current</Badge> : <Badge tone="gray">history</Badge>}</Td>
            </Tr>
          ))}
        </Table>
      </Card>

      {showNewCr && (
        <NewChangeRequestModal
          projectId={project.id}
          onClose={() => setShowNewCr(false)}
          onCreated={(cr) => {
            setShowNewCr(false);
            load();
            navigate(`/projects/${project.id}/changes/cr/${cr.id}`);
          }}
        />
      )}
    </div>
  );
}

function baselineVersion(name) {
  const m = /v?(\d+(?:\.\d+)?)/i.exec(name || "");
  return m ? `V${m[1]}` : name;
}
