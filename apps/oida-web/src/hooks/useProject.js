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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const pmAuthed = Boolean(session?.pm?.user);
  const qaAuthed = Boolean(session?.qa?.user);

  const load = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const [proj, homeData, baselinesData, pmHandoffs, qaHandoffs] = await Promise.all([
        documentApi.getProject(projectId),
        documentApi.projectHome(projectId).catch(() => null),
        documentApi.listBaselines(projectId).catch(() => []),
        documentApi.executionHandoffs(projectId).catch(() => []),
        documentApi.qaHandoffs(projectId).catch(() => []),
      ]);
      setProject(proj);
      setHome(homeData);
      setBaselines(baselinesData);

      // Workspace bindings are correlation metadata stored on the Document
      // project (authority keeps business truth). They make PM/QA resolution
      // deterministic instead of name/slug guessing.
      const bindings = proj?.metadata?.workspace_bindings || {};

      // PM project: prefer the stored binding; fall back to name matching.
      if (pmAuthed) {
        try {
          const boundSlug = bindings.pm_project_slug;
          let match = null;
          if (boundSlug) {
            match = await pmApi.getProject(boundSlug).then((p) => ({ name: p.name, slug: p.slug })).catch(() => null);
          }
          if (!match) {
            const pmProjects = await pmApi.listProjects();
            match = (pmProjects || []).find(
              (p) => (p.name || "").toLowerCase() === (proj.name || "").toLowerCase()
            );
          }
          setPm(match ? { name: match.name, slug: match.slug } : null);
        } catch {
          setPm(null);
        }
      } else {
        setPm(null);
      }

      // QA projects: one per Document QA handoff. Prefer the stored binding;
      // fall back to the slug derived from the handoff id.
      if (qaAuthed) {
        try {
          const qaProjects = await qaApi.listProjects();
          const baselineById = Object.fromEntries(
            (baselinesData || []).map((b) => [b.id, b])
          );
          const resolved = (qaHandoffs || []).map((h) => {
            const boundSlug = bindings.qa_project_slugs?.[h.id];
            const slugified = (h.id || "").toLowerCase().replace(/[^a-z0-9]+/g, "-");
            const fallbackSlug = `wp-${slugified}`;
            const found =
              (boundSlug && (qaProjects || []).find((p) => p.slug === boundSlug)) ||
              (qaProjects || []).find((p) => p.slug === fallbackSlug);
            const baseline = baselineById[h.baseline_id];
            return {
              handoffId: h.id,
              baselineId: h.baseline_id,
              baselineName: baseline ? baseline.name : h.baseline_id,
              releaseVersion: baseline ? baseline.target_release : null,
              requirementIds: h.requirement_ids || [],
              designRevisionIds: h.design_revision_ids || [],
              slug: found ? found.slug : (boundSlug || fallbackSlug),
              name: found ? found.name : null,
              status: h.status,
              linked: Boolean(found),
            };
          });
          resolved.sort((a, b) =>
            String(b.baselineName).localeCompare(String(a.baselineName), undefined, { numeric: true })
          );
          setQa(resolved);
        } catch {
          setQa([]);
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

  return { project, home, baselines, pm, qa, pmAuthed, qaAuthed, loading, error, reload: load };
}
