import { useEffect, useState } from "react";
import { qaApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, Loading, Empty, SignInPrompt, Table, Tr, Td, StatusBadge } from "../components/ui";

export default function QaTestCases() {
  const { qa, qaAuthed } = useProjectCtx();
  const currentQa = qa && qa.length ? qa[0] : null;
  const [suites, setSuites] = useState(null);

  useEffect(() => {
    if (currentQa?.slug) qaApi.suites(currentQa.slug).then(setSuites).catch(() => setSuites([]));
    else setSuites([]);
  }, [currentQa?.slug]);

  if (!qaAuthed) {
    return <SignInPrompt service="QA Again" children="Sign in to see test cases. Cases are created from a published script revision." />;
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold">Test Cases</h1>
        <p className="text-sm text-gray-500">Source: QA Again · no fabricated cases.</p>
      </div>

      <Card>
        <CardHeader title="Test suites" />
        {!suites ? (
          <Loading />
        ) : suites.length === 0 ? (
          <Empty title="No test cases yet">
            QA is waiting for test design. Cases are created from a published script revision.
          </Empty>
        ) : (
          <Table head={["Suite", "Type", "Status"]}>
            {suites.map((s) => (
              <Tr key={s.id}>
                <Td className="font-medium text-gray-800">{s.name}</Td>
                <Td className="text-gray-600">{s.suite_type}</Td>
                <Td><StatusBadge status={s.status} /></Td>
              </Tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
