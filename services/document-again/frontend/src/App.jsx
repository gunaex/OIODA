import React, { createContext, lazy, Suspense, useContext, useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { api } from "./api/client.js";
import { ContextPanel } from "./components/ContextPanel.jsx";

/*
 * Heavy workspace pages are code-split with React.lazy so the initial
 * bundle stays small and each design workspace loads only when opened.
 */
/*
 * React 19 `lazy` requires a default export, but these workspace pages export
 * a single named component (e.g. `export function Requirements`). Wrap the
 * dynamic import so the named component is surfaced as the default — without
 * this the app renders a blank page (P1 frontend fix).
 */
function lazyPage(loader, name) {
  return lazy(() => loader().then((m) => ({ default: m[name] })));
}

const Projects = lazyPage(() => import("./pages/Projects.jsx"), "Projects");
const ProjectHome = lazyPage(() => import("./pages/ProjectHome.jsx"), "ProjectHome");
const Requirements = lazyPage(() => import("./pages/Requirements.jsx"), "Requirements");
const Artifacts = lazyPage(() => import("./pages/Artifacts.jsx"), "Artifacts");
const Database = lazyPage(() => import("./pages/Database.jsx"), "Database");
const ChangeRequests = lazyPage(() => import("./pages/ChangeRequests.jsx"), "ChangeRequests");
const Baselines = lazyPage(() => import("./pages/Baselines.jsx"), "Baselines");
const Comments = lazyPage(() => import("./pages/Comments.jsx"), "Comments");
const Reviews = lazyPage(() => import("./pages/Reviews.jsx"), "Reviews");
const Compare = lazyPage(() => import("./pages/Compare.jsx"), "Compare");
const TraceExplorer = lazyPage(() => import("./pages/TraceExplorer.jsx"), "TraceExplorer");
const ImpactAnalysis = lazyPage(() => import("./pages/ImpactAnalysis.jsx"), "ImpactAnalysis");
const Search = lazyPage(() => import("./pages/Search.jsx"), "Search");
const FlowDesigner = lazyPage(() => import("./pages/FlowDesigner.jsx"), "FlowDesigner");
const ApiDesign = lazyPage(() => import("./pages/ApiDesign.jsx"), "ApiDesign");
const Architecture = lazyPage(() => import("./pages/Architecture.jsx"), "Architecture");
const Decisions = lazyPage(() => import("./pages/Decisions.jsx"), "Decisions");
const Ecosystem = lazyPage(() => import("./pages/Ecosystem.jsx"), "Ecosystem");
const Audit = lazyPage(() => import("./pages/Audit.jsx"), "Audit");

function PageFallback() {
  return <div className="p-10 text-[13px] text-slate-500">Loading workspace page…</div>;
}

/*
 * Workspace state: the active project and the "focus" semantic object
 * the right context panel (comments / trace / impact) is bound to.
 */
const WorkspaceCtx = createContext(null);
export const useWorkspace = () => useContext(WorkspaceCtx);

export default function App() {
  const [projects, setProjects] = useState(null);
  const [projectId, setProjectId] = useState(
    () => localStorage.getItem("da-project") || null
  );
  const [project, setProject] = useState(null);
  const [focus, setFocus] = useState(null); // { semanticId, label }

  useEffect(() => {
    api.get("/projects").then((rows) => {
      setProjects(rows);
      if (rows.length && !rows.some((p) => p.id === projectId)) {
        setProjectId(rows[0].id);
      }
    });
  }, []);

  useEffect(() => {
    if (!projectId || !projects) return;
    const found = projects.find((p) => p.id === projectId);
    setProject(found || null);
    if (found) localStorage.setItem("da-project", found.id);
  }, [projectId, projects]);

  if (projects === null) {
    return <div className="p-10 text-[13px] text-slate-500">Loading workspace…</div>;
  }

  if (projects.length === 0) {
    return <Projects onCreated={(p) => setProjects([p])} />;
  }

  const ws = {
    project,
    projects,
    setProjectId,
    focus,
    setFocus: (semanticId, label) => setFocus({ semanticId, label }),
  };

  return (
    <WorkspaceCtx.Provider value={ws}>
      <div className="flex h-screen flex-col">
        <Header />
        <div className="flex min-h-0 flex-1">
          <Nav />
          <main className="min-w-0 flex-1 overflow-y-auto p-4 xl:p-5">
            {project ? (
              <Suspense fallback={<PageFallback />}>
                <Routes>
                  <Route path="/" element={<ProjectHome />} />
                  <Route path="/requirements" element={<Requirements />} />
                  <Route path="/requirements/ur" element={<Artifacts type="UR" />} />
                  <Route path="/design/dr" element={<Artifacts type="DR" />} />
                  <Route path="/design/database/*" element={<Database />} />
                  <Route path="/design/compare" element={<Compare />} />
                  <Route path="/design/trace" element={<TraceExplorer />} />
                  <Route path="/design/impact" element={<ImpactAnalysis />} />
                  <Route path="/design/flows" element={<FlowDesigner />} />
                  <Route path="/design/apis" element={<ApiDesign />} />
                  <Route path="/design/architecture" element={<Architecture />} />
                  <Route path="/decisions" element={<Decisions />} />
                  <Route path="/reviews" element={<Reviews />} />
                  <Route path="/comments" element={<Comments />} />
                  <Route path="/change-requests" element={<ChangeRequests />} />
                  <Route path="/search" element={<Search />} />
                  <Route path="/baselines" element={<Baselines />} />
                  <Route path="/ecosystem" element={<Ecosystem />} />
                  <Route path="/audit" element={<Audit />} />
                </Routes>
              </Suspense>
            ) : (
              <p className="text-[13px] text-slate-500">Select a project…</p>
            )}
          </main>
          <ContextPanel />
        </div>
      </div>
    </WorkspaceCtx.Provider>
  );
}

function Header() {
  const { project, projects, setProjectId, focus } = useWorkspace();
  return (
    <header className="flex h-11 shrink-0 items-center justify-between border-b border-line bg-surface-1 px-3">
      <div className="flex items-center gap-3">
        <span className="rounded bg-brand-600 px-2 py-0.5 text-[12px] font-bold text-white">DA</span>
        <span className="text-[13px] font-semibold text-slate-200">Document Again</span>
        <span className="text-slate-600">/</span>
        {projects.length > 0 && (
          <select
            value={project?.id || ""}
            onChange={(e) => setProjectId(e.target.value)}
            className="rounded border border-line bg-surface-0 px-2 py-1 text-[12px] text-slate-300 outline-none"
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>{p.key} — {p.name}</option>
            ))}
          </select>
        )}
      </div>
      <div className="text-[12px] text-slate-500">
        {focus ? <span className="text-slate-400">focus: {focus.label}</span> : "files are outputs · structured design knowledge is the truth"}
      </div>
    </header>
  );
}

const NAV = [
  { section: "PROJECT" },
  { to: "/", label: "Project Home" },
  { to: "requirements", label: "Requirement Register" },
  { to: "requirements/ur", label: "UR" },
  { section: "DESIGN" },
  { to: "design/dr", label: "DR" },
  { to: "design/database", label: "Database" },
  { to: "design/flows", label: "Process Flows" },
  { to: "design/apis", label: "APIs" },
  { to: "design/architecture", label: "Architecture" },
  { to: "design/compare", label: "Compare" },
  { to: "design/trace", label: "Trace" },
  { to: "design/impact", label: "Impact" },
  { section: "GOVERNANCE" },
  { to: "decisions", label: "Decisions" },
  { to: "reviews", label: "Reviews" },
  { to: "comments", label: "Comments" },
  { to: "search", label: "Search" },
  { to: "change-requests", label: "Change Requests" },
  { to: "baselines", label: "Baselines" },
  { section: "ECOSYSTEM" },
  { to: "ecosystem", label: "Ecosystem Status" },
  { to: "audit", label: "Audit Trail" },
];

function Nav() {
  return (
    <nav className="w-56 shrink-0 space-y-0.5 overflow-y-auto border-r border-line bg-surface-1 p-2">
      {NAV.map((item, i) =>
        item.section ? (
          <p key={i} className="px-2 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-widest text-slate-600">
            {item.section}
          </p>
        ) : (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `block rounded px-2 py-1.5 text-[13px] ${
                isActive ? "bg-brand-600/20 text-brand-100" : "text-slate-400 hover:bg-surface-2 hover:text-slate-200"
              }`
            }
          >
            {item.label}
          </NavLink>
        )
      )}
    </nav>
  );
}
