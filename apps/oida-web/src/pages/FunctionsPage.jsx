import { useEffect, useState } from "react";
import { pmApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, StatusBadge, Loading, Empty, SignInPrompt, Table, Tr, Td } from "../components/ui";

export default function FunctionsPage() {
  const { pm, pmAuthed } = useProjectCtx();
  const [functions, setFunctions] = useState(null);

  useEffect(() => {
    if (pm?.slug) pmApi.functions(pm.slug).then(setFunctions).catch(() => setFunctions([]));
  }, [pm?.slug]);

  if (!pmAuthed) return <SignInPrompt service="PM Again" children="Sign in to see the workstreams materialized from the design baseline." />;
  if (!pm) return <Empty title="PM Again is not linked" />;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold">Functions / Workstreams</h1>
        <p className="text-sm text-gray-500">Materialized from the confirmed design baseline.</p>
      </div>

      <Card>
        <CardHeader title="Workstreams" />
        {!functions ? (
          <Loading />
        ) : functions.length === 0 ? (
          <Empty title="No workstreams" />
        ) : (
          <Table head={["Name", "Phase", "Owner", "Status"]}>
            {functions.map((f) => (
              <Tr key={f.id}>
                <Td className="font-medium text-gray-800">{f.name}</Td>
                <Td className="text-gray-600">{f.phase || "—"}</Td>
                <Td className="text-gray-600">{f.owner || "Unassigned"}</Td>
                <Td><StatusBadge status={f.status} /></Td>
              </Tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
