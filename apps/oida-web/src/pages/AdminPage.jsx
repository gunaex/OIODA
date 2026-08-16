import { useEffect, useState } from "react";
import { accountApi } from "../api";
import { Card, CardHeader, Loading, Table, Tr, Td, Badge } from "../components/ui";
import { Shield } from "lucide-react";

export default function AdminPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([
      accountApi.tenants().catch(() => []),
      accountApi.accounts().catch(() => []),
      accountApi.roles().catch(() => []),
      accountApi.productEntitlements().catch(() => []),
    ])
      .then(([tenants, accounts, roles, entitlements]) => setData({ tenants, accounts, roles, entitlements }))
      .catch(setError);
  }, []);

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <div className="flex items-center gap-2">
        <Shield size={20} className="text-gray-900" />
        <div>
          <h1 className="text-lg font-bold">Administration</h1>
          <p className="text-sm text-gray-500">Identity, tenants, roles and entitlements — backed by Account Again.</p>
        </div>
      </div>

      {error && <p className="text-sm text-rose-600">{String(error.message || error)}</p>}
      {!data && !error && <Loading />}

      {data && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader title="Organizations / Tenants" />
            <Table head={["Name", "Status"]}>
              {(data.tenants || []).map((t) => (
                <Tr key={t.tenantId || t.tenant_id}>
                  <Td className="font-medium text-gray-800">{t.name}</Td>
                  <Td><Badge tone="green">{t.status || "ACTIVE"}</Badge></Td>
                </Tr>
              ))}
            </Table>
          </Card>

          <Card>
            <CardHeader title="Users / Accounts" />
            <Table head={["Email", "Display name", "Status"]}>
              {(data.accounts || []).map((a) => (
                <Tr key={a.accountId || a.account_id}>
                  <Td className="text-gray-700">{a.email}</Td>
                  <Td className="text-gray-700">{a.displayName || a.display_name || "—"}</Td>
                  <Td><Badge tone="green">{a.status || "ACTIVE"}</Badge></Td>
                </Tr>
              ))}
            </Table>
          </Card>

          <Card>
            <CardHeader title="Roles" />
            <div className="flex flex-wrap gap-2 px-4 py-3">
              {(data.roles || []).map((r) => (
                <Badge key={r.roleId || r.role_id || r.name} tone="violet">{r.name}</Badge>
              ))}
            </div>
          </Card>

          <Card>
            <CardHeader title="Product entitlements" />
            <div className="px-4 py-3 text-sm text-gray-500">
              {(data.entitlements || []).length === 0
                ? "No product entitlements."
                : (data.entitlements || []).map((e) => (
                    <div key={e.entitlementId || e.entitlement_id} className="py-1">
                      <span className="text-gray-700">{e.productId || e.product_id || "—"}</span>{" "}
                      <Badge tone="green">{e.status || "ACTIVE"}</Badge>
                    </div>
                  ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
