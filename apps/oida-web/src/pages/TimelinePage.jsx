import { useEffect, useState } from "react";
import { pmApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, Loading, Empty, SignInPrompt, Table, Tr, Td, formatDate, Badge } from "../components/ui";

// Honest Timeline: no fabricated contractual dates. Renders the real PM Gantt
// bars if any exist, otherwise lists tasks in phase order with "Not Scheduled".
export default function TimelinePage() {
  const { pm, pmAuthed } = useProjectCtx();
  const [gantt, setGantt] = useState(null);
  const [tasks, setTasks] = useState(null);

  useEffect(() => {
    if (!pm?.slug) return;
    pmApi.gantt(pm.slug).then(setGantt).catch(() => setGantt([]));
    pmApi.tasks(pm.slug).then(setTasks).catch(() => setTasks([]));
  }, [pm?.slug]);

  if (!pmAuthed) return <SignInPrompt service="PM Again" children="Sign in to see the timeline. No dates are fabricated — everything stays unscheduled until a real plan provides them." />;
  if (!pm) return <Empty title="PM Again is not linked" />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold">Timeline</h1>
        <p className="text-sm text-gray-500">
          Logical phases are shown; dates remain unscheduled until a customer plan, PM or confirmed assumption provides them.
        </p>
      </div>

      <Card>
        <CardHeader title="Scheduled bars" subtitle="From PM Again Gantt (no fake dates)." />
        {!gantt ? (
          <Loading />
        ) : gantt.length === 0 ? (
          <div className="px-4 py-6 text-sm text-gray-500">
            Nothing scheduled yet. Fill dates later — nothing is invented here.
          </div>
        ) : (
          <Table head={["Name", "Phase", "Start", "End", "Progress"]}>
            {gantt.map((g) => (
              <Tr key={g.id}>
                <Td className="font-medium text-gray-800">{g.name}</Td>
                <Td><Badge tone="blue">{g.phase}</Badge></Td>
                <Td>{formatDate(g.start_date)}</Td>
                <Td>{formatDate(g.end_date)}</Td>
                <Td>{g.progress ?? 0}%</Td>
              </Tr>
            ))}
          </Table>
        )}
      </Card>

      <Card>
        <CardHeader title="Phase-ordered tasks" />
        {!tasks ? (
          <Loading />
        ) : (
          <ul className="divide-y divide-gray-50">
            {(tasks || []).map((t) => (
              <li key={t.id} className="flex items-center justify-between px-4 py-2.5 text-sm">
                <span className="text-gray-700">{t.title}</span>
                <span className="text-xs text-gray-400">{t.due_date ? formatDate(t.due_date) : "Not Scheduled"}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
