import { Link, Outlet, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import {
  LayoutDashboard,
  ClipboardList,
  FileText,
  Network,
  GitBranch,
  CalendarRange,
  CheckCircle2,
  History,
  Shield,
  LogOut,
  Boxes,
  Server,
  Sparkles,
  Layers,
  Users,
  Calculator,
  BarChart3,
  Bot,
} from "lucide-react";

function NavGroup({ title, children }) {
  return (
    <div className="mb-4">
      <div className="mb-1 px-3 text-[0.65rem] font-semibold uppercase tracking-wider text-gray-400">
        {title}
      </div>
      <nav className="space-y-0.5">{children}</nav>
    </div>
  );
}

function NavItem({ to, icon: Icon, label, parent = false }) {
  const { pathname } = useLocation();
  // Exact-match only is "active" — prevents a parent ("Projects",
  // "Planning", "QA Validation") from lighting up on its child routes.
  const isActive = pathname === to;
  // Only true parents get a subtle ancestor dot; siblings like "Overview"
  // must not look like they own the child route.
  const isAncestor = parent && !isActive && to !== "/" && pathname.startsWith(`${to}/`);

  return (
    <Link
      to={to}
      aria-current={isActive ? "page" : undefined}
      className={`relative flex items-center gap-2.5 rounded-lg px-3 py-1.5 text-[0.82rem] transition-colors ${
        isActive
          ? "bg-gray-100 font-medium text-gray-900"
          : isAncestor
          ? "text-gray-800"
          : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
      }`}
    >
      {isActive && (
        <span className="absolute left-0 top-1/2 h-3.5 w-[3px] -translate-y-1/2 rounded-full bg-gray-900" />
      )}
      {isAncestor && (
        <span className="absolute left-0 top-1/2 h-1.5 w-1.5 -translate-y-1/2 rounded-full bg-gray-300" />
      )}
      <Icon size={15} strokeWidth={isActive ? 2.2 : 1.8} />
      {label}
    </Link>
  );
}

export default function Layout({ project, projectId }) {
  const { session, logout } = useAuth();
  const navigate = useNavigate();
  const base = `/projects/${projectId}`;

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-60 shrink-0 flex-col border-r border-gray-200 bg-white">
        <div className="flex items-center gap-2 px-4 py-4">
          <Boxes size={20} className="text-gray-900" />
          <div>
            <div className="text-sm font-bold tracking-tight">OIDA OS</div>
            <div className="text-[0.65rem] text-gray-400">Project Delivery Workspace</div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-2 pb-4">
          <NavGroup title="Project">
            <NavItem to="/projects" icon={LayoutDashboard} label="Projects" parent />
            {projectId && (
              <>
                <NavItem to={base} icon={LayoutDashboard} label="Overview" />
                <NavItem to={`${base}/deliverables`} icon={ClipboardList} label="Documents" />
              </>
            )}
          </NavGroup>

          {projectId && (
            <>
              <NavGroup title="Requirements">
                <NavItem to={`${base}/requirements`} icon={ClipboardList} label="Requirement Register" parent />
                <NavItem to={`${base}/suggestions`} icon={Sparkles} label="OIDA Suggestions" />
                <NavItem to={`${base}/context-inspector`} icon={Sparkles} label="Context Inspector" />
              </NavGroup>
              <NavGroup title="Documents">
                <NavItem to={`${base}/documents/ur`} icon={FileText} label="UR" />
                <NavItem to={`${base}/documents/dr`} icon={FileText} label="DR" />
                <NavItem to={`${base}/architecture`} icon={Network} label="Architecture" />
                <NavItem to={`${base}/trace`} icon={GitBranch} label="Traceability" />
              </NavGroup>
              <NavGroup title="Planning">
                <NavItem to={`${base}/planning`} icon={CalendarRange} label="Planning" parent />
                <NavItem to={`${base}/planning/functions`} icon={CalendarRange} label="Functions" />
                <NavItem to={`${base}/planning/timeline`} icon={CalendarRange} label="Timeline" />
                <NavItem to={`${base}/planning/tasks`} icon={CalendarRange} label="Tasks" />
                <NavItem to={`${base}/planning/board`} icon={Layers} label="Board" />
                <NavItem to={`${base}/planning/notes`} icon={FileText} label="Notes" />
                <NavItem to={`${base}/planning/resources`} icon={Users} label="Resources" />
                <NavItem to={`${base}/planning/effort`} icon={Calculator} label="Effort" />
                <NavItem to={`${base}/planning/reports`} icon={BarChart3} label="Reports" />
              </NavGroup>
              <NavGroup title="QA">
                <NavItem to={`${base}/qa`} icon={CheckCircle2} label="QA Validation" parent />
                <NavItem to={`${base}/qa/test-cases`} icon={CheckCircle2} label="Test Cases" />
                <NavItem to={`${base}/qa/test-runs`} icon={CheckCircle2} label="Test Runs" />
                <NavItem to={`${base}/qa/evidence`} icon={CheckCircle2} label="Evidence" />
                <NavItem to={`${base}/qa/suites`} icon={CheckCircle2} label="Suites" />
                <NavItem to={`${base}/qa/cycles`} icon={CheckCircle2} label="Cycles" />
                <NavItem to={`${base}/qa/defects`} icon={CheckCircle2} label="Defects" />
                <NavItem to={`${base}/qa/reports`} icon={CheckCircle2} label="Reports" />
              </NavGroup>
              <NavGroup title="Infrastructure">
                <NavItem to={`${base}/infra-again`} icon={Server} label="Infra Workspace" parent />
                <NavItem to={`${base}/infrastructure`} icon={Server} label="Design Arch" />
              </NavGroup>
              <NavGroup title="Council">
                <NavItem to={`${base}/council`} icon={Bot} label="Council" parent />
              </NavGroup>
              <NavGroup title="Changes & History">
                <NavItem to={`${base}/changes`} icon={GitBranch} label="Changes" />
                <NavItem to={`${base}/history`} icon={History} label="History" />
              </NavGroup>
            </>
          )}

          <NavGroup title="Administration">
            <NavItem to={`${base}/admin`} icon={Shield} label="Users & Roles" />
            <NavItem to={`${base}/admin/ai-providers`} icon={Sparkles} label="AI Providers" />
          </NavGroup>
        </div>

        <div className="border-t border-gray-100 px-4 py-3 text-xs text-gray-500">
          <div className="truncate font-medium text-gray-700">
            {session.pm?.user?.email || session.qa?.user?.email || "Local workspace"}
          </div>
          <button
            onClick={async () => {
              await logout();
              navigate("/login");
            }}
            className="mt-1.5 inline-flex items-center gap-1 text-gray-400 hover:text-gray-700"
          >
            <LogOut size={13} /> Sign out
          </button>
        </div>
      </aside>

      <main className="min-w-0 flex-1">
        <header className="sticky top-0 z-10 flex h-12 items-center border-b border-gray-200 bg-white/90 px-6 backdrop-blur">
          <div className="flex min-w-0 items-center gap-2 text-sm">
            <Link to="/projects" className="text-gray-400 hover:text-gray-700">Projects</Link>
            {project && (
              <>
                <span className="text-gray-300">/</span>
                <span className="truncate font-medium text-gray-800">{project.name}</span>
              </>
            )}
          </div>
        </header>
        <div className="mx-auto max-w-6xl px-6 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
