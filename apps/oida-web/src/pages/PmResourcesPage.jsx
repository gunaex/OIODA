import { useEffect, useState } from "react";
import { pmApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, Loading, Empty, Table, Tr, Td } from "../components/ui";

export default function PmResourcesPage() {
  const { pm } = useProjectCtx();
  const [resources, setResources] = useState(null);
  const [allocations, setAllocations] = useState(null);

  useEffect(() => {
    pmApi.resources().then(setResources).catch(() => setResources([]));
    if (pm?.slug) pmApi.resourceAllocations(pm.slug).then(setAllocations).catch(() => setAllocations([]));
  }, [pm?.slug]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold">Resources</h1>
        <p className="text-sm text-gray-500">Company resource pool and project allocations. Authority: PM Again (read-only in OIDA).</p>
      </div>

      <Card>
        <CardHeader title={`Resource pool (${resources?.length ?? "…"})`} />
        {!resources ? <Loading /> : resources.length === 0 ? <Empty title="No resources" /> : (
          <Table head={["Name", "Role", "Capacity (h/wk)"]}>
            {resources.map((r) => (
              <Tr key={r.id}>
                <Td className="font-medium text-gray-800">{r.name}</Td>
                <Td className="text-gray-600">{r.role}</Td>
                <Td className="text-gray-600">{r.weekly_capacity_hours ?? "—"}</Td>
              </Tr>
            ))}
          </Table>
        )}
      </Card>

      <Card>
        <CardHeader title={`Project allocations (${allocations?.length ?? "…"})`} />
        {!allocations ? <Loading /> : allocations.length === 0 ? <Empty title="No allocations" /> : (
          <Table head={["Resource", "Percent", "Start", "End"]}>
            {allocations.map((a) => (
              <Tr key={a.id}>
                <Td className="font-medium text-gray-800">{a.resource_id}</Td>
                <Td className="text-gray-600">{a.allocation_percent}%</Td>
                <Td className="text-gray-600">{a.start_date || "—"}</Td>
                <Td className="text-gray-600">{a.end_date || "—"}</Td>
              </Tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
