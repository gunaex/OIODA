import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { documentApi, pmApi, qaApi } from "../api";
import { useAuth } from "../auth/AuthContext";

const ProjectContext = createContext(null);
export function useProjectCtx() {
  return useContext(ProjectContext);
}
export { ProjectContext };

// Resolves the unified project context: the Document Again project is the
// master; PM and QA projects are located via human name / handoff ids so the
// owner never sees technical slugs or IDs.
export function useProject(projectId) {
  const { session } = useAuth();
  const [project, setProject] = useState(null);
  const [home, setHome] = useState(null);
  const [baselines, setBaselines] = useState([]);
  const [pm, setPm] = useState(null); // { name, slug }
  const [qa, setQa] = useState([]); // [{ handoffId, baselineId, slug, name }]
  const [pmError, setPmError] = useState(null);
  const [qaError, setQaError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const pmAuthed = Boolean(session?.pm?.user);
  const qaAuthed = Boolean(session?.qa?.user);

  const load = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const [proj, homeData, baselinesData, bindingsResponse, qaHandoffs] = await Promise.all([
        documentApi.getProject(projectId),
        documentApi.projectHome(projectId).catch(() => null),
        documentApi.listBaselines(projectId).catch(() => []),
        documentApi.getWorkspaceBindings(projectId),
        documentApi.qaHandoffs(projectId).catch(() => []),
      ]);
      setProject(proj);
      setHome(homeData);
      setBaselines(baselinesData);

      // Workspace bindings are correlation metadata stored on the Document
      // project (authority keeps business truth). They make PM/QA resolution
      // deterministic instead of name/slug guessing.
      const bindings = bindingsResponse?.binding_contract || {};

      // Project identity is explicit. Display names and slugs are never used
      // to infer a binding.
      if (pmAuthed) {
        try {
          setPmError(null);
          const boundSlug = bindings.pm?.external_project_id;
          const match = boundSlug
            ? await pmApi.getProject(boundSlug).then((p) => ({ name: p.name, slug: p.slug }))
            : null;
          setPm(match ? { name: match.name, slug: match.slug } : null);
        } catch (err) {
          setPm(null);
          setPmError(err);
        }
      } else {
        setPm(null);
      }

      // QA projects: one per explicit binding; handoff IDs only label scope.
      if (qaAuthed) {
        try {
          setQaError(null);
          const qaProjects = await qaApi.listProjects();
          const explicit = Object.fromEntries((bindings.qa || []).map((b) => [b.scope_id, b.external_project_id]));
          const baselineById = Object.fromEntries(
            (baselinesData || []).map((b) => [b.id, b])
          );
          const resolved = (qaHandoffs || []).map((h) => {
            const boundSlug = explicit[h.id];
            const found = boundSlug && (qaProjects || []).find((p) => p.slug === boundSlug);
            const baseline = baselineById[h.baseline_id];
            return {
              handoffId: h.id,
              baselineId: h.baseline_id,
              baselineName: baseline ? baseline.name : h.baseline_id,
              releaseVersion: baseline ? baseline.target_release : null,
              requirementIds: h.requirement_ids || [],
              designRevisionIds: h.design_revision_ids || [],
              // A derived slug is a lookup hint, not authoritative identity.
              // Do not expose it as a usable binding when QA has no project.
              slug: found ? found.slug : null,
              name: found ? found.name : null,
              status: h.status,
              linked: Boolean(found),
            };
          });
          resolved.sort((a, b) =>
            String(b.baselineName).localeCompare(String(a.baselineName), undefined, { numeric: true })
          );
          setQa(resolved);
        } catch (err) {
          setQa([]);
          setQaError(err);
        }
      } else {
        setQa([]);
      }
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [projectId, pmAuthed, qaAuthed]);

  useEffect(() => {
    load();
  }, [load]);

  return { project, home, baselines, pm, qa, pmAuthed, qaAuthed, pmError, qaError, loading, error, reload: load };
}
