import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { documentApi, qaApi } from "../api";
import { useProjectCtx } from "../hooks/useProject";
import { Card, CardHeader, StatusBadge, Badge, Loading, Empty, SignInPrompt, Table, Tr, Td } from "../components/ui";

export default function QaPage() {
  const { project, qa, qaAuthed } = useProjectCtx();
  const [requirements, setRequirements] = useState(null);
  const [memory, setMemory] = useState(null);
  const [qaDashboard, setQaDashboard] = useState(null);

  const currentQa = qa && qa.length ? qa[0] : null;

  useEffect(() => {
    if (!project) return;
    documentApi.listRequirements(project.id).then(setRequirements).catch(() => setRequirements([]));
    documentApi.projectMemory(project.id).then(setMemory).catch(() => setMemory(null));
    if (currentQa?.slug) {
      qaApi.dashboard(currentQa.slug).then(setQaDashboard).catch(() => setQaDashboard(null));
    }
  }, [project?.id, currentQa?.slug]);

  if (!project) return <Loading />;
  if (!qaAuthed) {
    return <SignInPrompt service="QA Again" children="Sign in to see the validation scope and its honest state." />;
  }

  const scopeIds = new Set(currentQa?.requirementIds || []);
  const inScope = (requirements || []).filter((r) => scopeIds.size === 0 || scopeIds.has(r.id));
  const clarifications = (memory?.clarifications || []).filter((c) => !c.resolved);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold">QA Validation</h1>
        <p className="text-sm text-gray-500">
          {currentQa ? `Baseline ${baselineLabel(currentQa.baselineName)} · Source: QA Again` : "QA Again not linked"}
        </p>
      </div>

      {!currentQa && <Empty title="No QA validation scope linked to this project" />}

      {currentQa && (
        <>
          <Card>
            <CardHeader title="Validation state" />
            <div className="grid grid-cols-2 gap-3 px-4 py-3 md:grid-cols-4">
              <StateItem k="Scope" v={<StatusBadge status={qaDashboard?.activeCycle ? "Ready" : "Received"} />} />
              <StateItem k="Test cases" v={qaDashboard?.activeCycle?.testCaseCount ?? 0} />
              <StateItem k="Executed" v="0 — none run yet" />
              <StateItem k="Why waiting" v="Awaiting test design (no published script revision)" />
            </div>
          </Card>

          <Card>
            <CardHeader title="Validation Scope" subtitle={`${inScope.length} requirements from the design baseline`} />
            {!requirements ? (
              <Loading />
            ) : (
              <Table head={["Requirement", "Title", "QA Status"]}>
                {inScope.map((r) => (
                  <Tr key={r.id}>
                    <Td>
                      <Link to={`/projects/${project.id}/requirements/${r.code}`} className="font-semibold text-gray-900 hover:underline">
                        {r.code}
                      </Link>
                    </Td>
                    <Td className="text-gray-700">{r.title}</Td>
                    <Td><StatusBadge status="Waiting for test design" /></Td>
                  </Tr>
                ))}
              </Table>
            )}
          </Card>

          {clarifications.length > 0 && (
            <Card>
              <CardHeader title="Open clarifications blocking verification" />
              <ul className="divide-y divide-gray-50 px-4 py-2">
                {clarifications.map((c) => (
                  <li key={c.semantic_id || c.id} className="py-2 text-sm text-gray-700">{c.question}</li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

function StateItem({ k, v }) {
  return (
    <div>
      <div className="text-xs font-medium uppercase tracking-wide text-gray-400">{k}</div>
      <div className="mt-1 text-sm text-gray-700">{v}</div>
    </div>
  );
}

function baselineLabel(name) {
  const m = /v?(\d+(?:\.\d+)?)/i.exec(name || "");
  return m ? m[1] : "—";
}
