import { useEffect, useState } from "react";
import { qaApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, Loading, Empty, SignInPrompt, Table, Tr, Td, StatusBadge, formatDateTime } from "../components/ui";

export default function QaTestRuns() {
  const { qa, qaAuthed } = useProjectCtx();
  const currentQa = qa && qa.length ? qa[0] : null;
  const [cycles, setCycles] = useState(null);

  useEffect(() => {
    if (currentQa?.slug) qaApi.cycles(currentQa.slug).then(setCycles).catch(() => setCycles([]));
    else setCycles([]);
  }, [currentQa?.slug]);

  if (!qaAuthed) {
    return <SignInPrompt service="QA Again" children="Sign in to see test runs. PASS requires evidence — no result is fabricated." />;
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold">Test Runs</h1>
        <p className="text-sm text-gray-500">Source: QA Again · PASS requires evidence.</p>
      </div>

      <Card>
        <CardHeader title="Test cycles" />
        {!cycles ? (
          <Loading />
        ) : cycles.length === 0 ? (
          <Empty title="No test runs yet">
            A test run is created from a published script revision. None exists for this baseline yet — QA has not fabricated a result.
          </Empty>
        ) : (
          <Table head={["Cycle", "Environment", "Release", "Status", "Started"]}>
            {cycles.map((c) => (
              <Tr key={c.id}>
                <Td className="font-medium text-gray-800">{c.name || c.cycle_code}</Td>
                <Td className="text-gray-600">{c.environment}</Td>
                <Td className="text-gray-600">{c.release_version || "—"}</Td>
                <Td><StatusBadge status={c.status} /></Td>
                <Td className="text-gray-600">{formatDateTime(c.started_at)}</Td>
              </Tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
