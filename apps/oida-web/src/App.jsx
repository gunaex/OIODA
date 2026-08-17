import { Routes, Route, Navigate, useParams, useLocation } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import Layout from "./components/Layout";
import { useProject, ProjectContext } from "./hooks/useProject";
import { Loading, OidaError } from "./components/ui";

import Login from "./pages/Login";
import Projects from "./pages/Projects";
import ProjectHome from "./pages/ProjectHome";
import Requirements from "./pages/Requirements";
import RequirementDetail from "./pages/RequirementDetail";
import UrPage from "./pages/UrPage";
import DrPage from "./pages/DrPage";
import ArchitecturePage from "./pages/ArchitecturePage";
import TracePage from "./pages/TracePage";
import PlanningPage from "./pages/PlanningPage";
import FunctionsPage from "./pages/FunctionsPage";
import TimelinePage from "./pages/TimelinePage";
import TasksPage from "./pages/TasksPage";
import PmBoardPage from "./pages/PmBoardPage";
import PmNotesPage from "./pages/PmNotesPage";
import PmResourcesPage from "./pages/PmResourcesPage";
import PmEffortPage from "./pages/PmEffortPage";
import PmReportsPage from "./pages/PmReportsPage";
import QaPage from "./pages/QaPage";
import QaTestCases from "./pages/QaTestCases";
import QaTestRuns from "./pages/QaTestRuns";
import QaEvidence from "./pages/QaEvidence";
import QaSuitesPage from "./pages/QaSuitesPage";
import QaCyclesPage from "./pages/QaCyclesPage";
import QaDefectsPage from "./pages/QaDefectsPage";
import QaReportsPage from "./pages/QaReportsPage";
import ChangesPage from "./pages/ChangesPage";
import ChangeDetailPage from "./pages/ChangeDetailPage";
import ChangeRequestDetailPage from "./pages/ChangeRequestDetailPage";
import InfrastructurePage from "./pages/InfrastructurePage";
import InfraAgainPage from "./pages/InfraAgainPage";
import CouncilPage from "./pages/CouncilPage";
import SuggestionsPage from "./pages/SuggestionsPage";
import AiProvidersPage from "./pages/AiProvidersPage";
import ContextInspectorPage from "./pages/ContextInspectorPage";
import HistoryPage from "./pages/HistoryPage";
import AdminPage from "./pages/AdminPage";

function ProjectLayout() {
  const { projectId } = useParams();
  const ctx = useProject(projectId);
  const { project, loading, error, reload } = ctx;
  if (loading) return <Loading />;
  if (error) return <OidaError message={String(error.message || error)} onRetry={reload} />;
  return (
    <ProjectContext.Provider value={ctx}>
      <Layout project={project} projectId={projectId} />
    </ProjectContext.Provider>
  );
}

function RequireAuth({ children }) {
  const { loading, authenticated } = useAuth();
  const location = useLocation();
  // Never render protected content while auth state is unresolved.
  if (loading) return <Loading />;
  if (!authenticated) {
    const returnTo = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?returnTo=${returnTo}`} replace />;
  }
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Navigate to="/projects" replace />} />
      <Route
        path="/projects"
        element={
          <RequireAuth>
            <Projects />
          </RequireAuth>
        }
      />
      <Route path="/admin" element={<Navigate to="/projects" replace />} />
      <Route path="/admin/ai-providers" element={<Navigate to="/projects" replace />} />
      <Route element={<RequireAuth><ProjectLayout /></RequireAuth>}>
        <Route path="/projects/:projectId" element={<ProjectHome />} />
        <Route path="/projects/:projectId/requirements" element={<Requirements />} />
        <Route path="/projects/:projectId/requirements/:code" element={<RequirementDetail />} />
        <Route path="/projects/:projectId/documents/ur" element={<UrPage />} />
        <Route path="/projects/:projectId/documents/dr" element={<DrPage />} />
        <Route path="/projects/:projectId/architecture" element={<ArchitecturePage />} />
        <Route path="/projects/:projectId/trace" element={<TracePage />} />
        <Route path="/projects/:projectId/planning" element={<PlanningPage />} />
        <Route path="/projects/:projectId/planning/functions" element={<FunctionsPage />} />
        <Route path="/projects/:projectId/planning/timeline" element={<TimelinePage />} />
        <Route path="/projects/:projectId/planning/tasks" element={<TasksPage />} />
        <Route path="/projects/:projectId/planning/board" element={<PmBoardPage />} />
        <Route path="/projects/:projectId/planning/notes" element={<PmNotesPage />} />
        <Route path="/projects/:projectId/planning/resources" element={<PmResourcesPage />} />
        <Route path="/projects/:projectId/planning/effort" element={<PmEffortPage />} />
        <Route path="/projects/:projectId/planning/reports" element={<PmReportsPage />} />
        <Route path="/projects/:projectId/qa" element={<QaPage />} />
        <Route path="/projects/:projectId/qa/test-cases" element={<QaTestCases />} />
        <Route path="/projects/:projectId/qa/test-runs" element={<QaTestRuns />} />
        <Route path="/projects/:projectId/qa/evidence" element={<QaEvidence />} />
        <Route path="/projects/:projectId/qa/suites" element={<QaSuitesPage />} />
        <Route path="/projects/:projectId/qa/cycles" element={<QaCyclesPage />} />
        <Route path="/projects/:projectId/qa/defects" element={<QaDefectsPage />} />
        <Route path="/projects/:projectId/qa/reports" element={<QaReportsPage />} />
        <Route path="/projects/:projectId/changes" element={<ChangesPage />} />
        <Route path="/projects/:projectId/changes/:changeId" element={<ChangeDetailPage />} />
        <Route path="/projects/:projectId/changes/cr/:crId" element={<ChangeRequestDetailPage />} />
        <Route path="/projects/:projectId/infrastructure" element={<InfrastructurePage />} />
        <Route path="/projects/:projectId/infra-again" element={<InfraAgainPage />} />
        <Route path="/projects/:projectId/council" element={<CouncilPage />} />
        <Route path="/projects/:projectId/suggestions" element={<SuggestionsPage />} />
        <Route path="/projects/:projectId/context-inspector" element={<ContextInspectorPage />} />
        <Route path="/projects/:projectId/history" element={<HistoryPage />} />
        <Route path="/projects/:projectId/admin" element={<AdminPage />} />
        <Route path="/projects/:projectId/admin/ai-providers" element={<AiProvidersPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/projects" replace />} />
    </Routes>
  );
}
