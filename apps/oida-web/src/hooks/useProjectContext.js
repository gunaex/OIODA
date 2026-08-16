// Shared cross-service context loader for OIDA Council / Context Inspector.
// Loads Document + PM + QA + Infra truth and exposes a buildEnvelope(question)
// that produces the normalized Context Envelope via contextBuilder.
import { useEffect, useState } from "react";
import { documentApi, pmApi, qaApi, infraApi } from "../api";
import { buildContextEnvelope } from "../lib/contextBuilder";

export function useProjectContext(project, pm, qa) {
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!project) return;
    const qaSlug = qa?.length ? qa[0].slug : null;
    Promise.all([
      documentApi.listRequirements(project.id).catch(() => []),
      documentApi.projectMemory(project.id).catch(() => null),
      documentApi.traceGraph(project.id).catch(() => ({ edges: [] })),
      pm?.slug ? pmApi.tasks(pm.slug).catch(() => []) : Promise.resolve([]),
      pm?.slug ? pmApi.effortSummary(pm.slug).catch(() => null) : Promise.resolve(null),
      pm?.slug ? pmApi.resources().catch(() => []) : Promise.resolve([]),
      qaSlug ? qaApi.defects(qaSlug).catch(() => []) : Promise.resolve([]),
      qaSlug ? qaApi.suites(qaSlug).catch(() => []) : Promise.resolve([]),
      qaSlug ? qaApi.cycles(qaSlug).catch(() => []) : Promise.resolve([]),
      Promise.resolve([]),
      infraApi.environments().catch(() => []),
      infraApi.designs().catch(() => []),
      infraApi.executionRuns().catch(() => []),
      documentApi.getWorkspaceBindings(project.id).catch(() => null),
    ]).then(([requirements, memory, trace, pmTasks, pmEffort, pmResources, qaDefects, qaSuites, qaCycles, _ignored, infraEnvs, infraDesigns, infraRuns, bindings]) => {
      const boundPromise = bindings?.infra_design_id
        ? infraApi.getDesign(bindings.infra_design_id).catch(() => null)
        : Promise.resolve(null);
      const firstCycle = qaCycles && qaCycles[0];
      const execPromise = qaSlug && firstCycle
        ? qaApi.cycleResults(qaSlug, firstCycle.id).catch(() => [])
        : Promise.resolve([]);
      const casesPromise = (async () => {
        if (!qaSlug) return [];
        const cases = [];
        for (const s of (qaSuites || []).slice(0, 2)) {
          const revs = await qaApi.revisions(qaSlug, s.id).catch(() => []);
          const pub = (revs || []).find((r) => r.status === "PUBLISHED");
          if (pub) {
            cases.push(...(await qaApi.cases(qaSlug, pub.id).catch(() => [])));
            break;
          }
        }
        return cases;
      })();
      Promise.all([execPromise, casesPromise, boundPromise]).then(([executions, qaCases, boundDesign]) => {
        const toArr = (v, key) => (Array.isArray(v) ? v : Array.isArray(v && v[key]) ? v[key] : []);
        setData({
          requirements, memory, trace: trace.edges || [], pmTasks, pmEffort, pmResources,
          qaDefects, qaSuites, qaCases, qaCycles, qaExecutions: executions,
          infra: {
            environments: toArr(infraEnvs, "environments"),
            designs: toArr(infraDesigns, "designs"),
            executionRuns: toArr(infraRuns, "executionRuns"),
            boundDesign: boundDesign?.design || boundDesign || null,
          },
        });
      });
    });
  }, [project?.id, pm?.slug, qa?.length]);

  function buildEnvelope(question) {
    if (!data) return null;
    return buildContextEnvelope({
      project,
      question,
      requirements: data.requirements,
      clarifications: data.memory?.clarifications || [],
      assumptions: data.memory?.assumptions || [],
      decisions: data.memory?.decisions || [],
      pmTasks: data.pmTasks,
      pmEffort: data.pmEffort,
      pmResources: data.pmResources,
      qaDefects: data.qaDefects,
      qaSuites: data.qaSuites,
      qaCases: data.qaCases,
      qaCycles: data.qaCycles,
      qaExecutions: data.qaExecutions,
      infra: data.infra,
      traceEdges: data.trace,
    });
  }

  return { data, buildEnvelope };
}
