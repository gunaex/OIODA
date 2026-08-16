import { useEffect, useState } from "react";
import { documentApi, pmApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, Loading, Badge, formatDateTime } from "../components/ui";

export default function HistoryPage() {
  const { project, baselines, pm } = useProjectCtx();
  const [timeline, setTimeline] = useState(null);
  const [events, setEvents] = useState(null);
  const [pmActivity, setPmActivity] = useState(null);

  useEffect(() => {
    if (!project) return;
    documentApi.timeline(project.id).then(setTimeline).catch(() => setTimeline([]));
    documentApi.ecosystemEvents(project.id).then(setEvents).catch(() => setEvents([]));
    if (pm?.slug) pmApi.activity(pm.slug).then(setPmActivity).catch(() => setPmActivity([]));
  }, [project?.id, pm?.slug]);

  if (!project) return <Loading />;

  const activity = [
    ...(Array.isArray(timeline) ? timeline : []).map((e) => ({
      kind: "Document Again",
      text: e.label || e.description || e.action || e.event_type || e.kind || "Activity",
      at: e.at || e.timestamp || e.created_at,
    })),
    ...(Array.isArray(events) ? events : []).map((e) => ({
      kind: "Conductor",
      text: `${e.event_type} (correlation ${e.correlation_id || "—"})`,
      at: e.created_at,
    })),
    ...(Array.isArray(pmActivity) ? pmActivity : []).map((e) => ({
      kind: "PM Again",
      text: `${e.entity_type || "item"} changed ${e.field_changed || ""}`,
      at: e.changed_at,
    })),
  ].sort((a, b) => String(b.at || "").localeCompare(String(a.at || "")));

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold">History</h1>
        <p className="text-sm text-gray-500">Recent activity, revision history and audit trail.</p>
      </div>

      <Card>
        <CardHeader title="Baseline history" />
        <div className="px-4 py-3">
          {(baselines || []).map((b) => (
            <div key={b.id} className="flex items-center justify-between border-b border-gray-50 py-2 text-sm last:border-0">
              <span className="font-medium text-gray-800">{b.name}</span>
              <span className="text-xs text-gray-400">{b.description || "—"}</span>
            </div>
          ))}
          {(!baselines || baselines.length === 0) && <p className="text-sm text-gray-500">No baselines.</p>}
        </div>
      </Card>

      <Card>
        <CardHeader title="Activity stream" subtitle="Composed from Document Again, Conductor and PM Again." />
        <ul className="divide-y divide-gray-50">
          {activity.length === 0 ? (
            <li className="px-4 py-6 text-sm text-gray-500">No activity.</li>
          ) : (
            activity.slice(0, 40).map((a, i) => (
              <li key={i} className="flex items-start gap-3 px-4 py-2.5 text-sm">
                <Badge tone={a.kind === "PM Again" ? "amber" : a.kind === "Conductor" ? "violet" : "blue"}>{a.kind}</Badge>
                <span className="flex-1 text-gray-700">{a.text}</span>
                <span className="shrink-0 text-xs text-gray-400">{formatDateTime(a.at)}</span>
              </li>
            ))
          )}
        </ul>
      </Card>
    </div>
  );
}
