import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { pmApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, StatCard, StatusBadge, Loading, Empty, SignInPrompt, formatDate } from "../components/ui";

export default function PlanningPage() {
  const { project, pm, pmAuthed } = useProjectCtx();
  const [functions, setFunctions] = useState(null);
  const [tasks, setTasks] = useState(null);

  useEffect(() => {
    if (!pm?.slug) return;
    pmApi.functions(pm.slug).then(setFunctions).catch(() => setFunctions([]));
    pmApi.tasks(pm.slug).then(setTasks).catch(() => setTasks([]));
  }, [pm?.slug]);

  if (!pmAuthed) {
    return <SignInPrompt service="PM Again" children="Sign in to see workstreams, tasks and timeline. Dates stay unscheduled until a plan provides evidence." />;
  }
  if (!pm) {
    return <Empty title="PM Again is not linked to this project" children="Materialize the execution plan to see planning." />;
  }

  const done = (tasks || []).filter((t) => t.status === "Done").length;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold">Planning</h1>
        <p className="text-sm text-gray-500">Source: PM Again · Dates remain unscheduled until a plan provides evidence.</p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard label="Workstreams" value={functions?.length ?? "…"} />
        <StatCard label="Tasks" value={tasks?.length ?? "…"} />
        <StatCard label="Done" value={done} tone="green" />
        <StatCard label="Scheduled" value="0" sub="No dates yet — honest" tone="amber" />
      </div>

      <Card>
        <CardHeader title="Workstreams (Tracks)" right={<Link to={`/projects/${project.id}/planning/functions`} className="text-xs font-medium text-gray-500 hover:text-gray-800">Open Functions →</Link>} />
        <div className="px-4 py-3">
          {!functions ? (
            <Loading />
          ) : functions.length === 0 ? (
            <p className="text-sm text-gray-500">No workstreams yet.</p>
          ) : (
            <div className="space-y-2">
              {functions.map((f) => {
                const count = (tasks || []).filter((t) => t.linked_function_id === f.id).length;
                return (
                  <div key={f.id} className="flex items-center justify-between rounded-lg border border-gray-100 px-3 py-2.5">
                    <div>
                      <div className="text-sm font-semibold text-gray-800">{f.name}</div>
                      <div className="text-xs text-gray-400">{count} requirement-backed tasks</div>
                    </div>
                    <StatusBadge status={f.status} />
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </Card>

      <Card>
        <CardHeader title="Tasks" right={<Link to={`/projects/${project.id}/planning/tasks`} className="text-xs font-medium text-gray-500 hover:text-gray-800">Open Tasks →</Link>} />
        <div className="px-4 py-3">
          {!tasks ? (
            <Loading />
          ) : (
            <ul className="divide-y divide-gray-50">
              {(tasks || []).slice(0, 8).map((t) => (
                <li key={t.id} className="flex items-center justify-between py-2 text-sm">
                  <span className="text-gray-700">{t.title}</span>
                  <span className="flex items-center gap-3 text-xs text-gray-400">
                    {t.due_date ? formatDate(t.due_date) : "Not Scheduled"}
                    <StatusBadge status={t.status} />
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Card>
    </div>
  );
}
