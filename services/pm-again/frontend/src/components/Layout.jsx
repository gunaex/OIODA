import { useEffect, useState } from 'react'
import { NavLink, Outlet, useParams } from 'react-router-dom'
import { getProject } from '../api/client'
import { useAuth } from '../auth/AuthContext.jsx'
import SearchBar from './SearchBar.jsx'
import QuickNoteBar from './QuickNoteBar.jsx'
import UserBadge from './UserBadge.jsx'
import EcosystemStatusIndicator from './EcosystemStatusIndicator.jsx'

const tabClass = ({ isActive }) =>
  `px-4 py-2 rounded-md text-sm font-medium ${
    isActive ? 'bg-indigo-600 text-white' : 'text-gray-600 hover:bg-gray-100'
  }`

export default function Layout() {
  const { slug } = useParams()
  const { user } = useAuth()
  // UX-only: the backend RBAC (see security spec) is what actually enforces
  // client_viewer being blocked from these modules — this just avoids
  // sending them to a tab that always 403s.
  const isClientViewer = user?.role === 'client_viewer'
  const [project, setProject] = useState(null)
  const [projectLoadError, setProjectLoadError] = useState(false)

  useEffect(() => {
    setProjectLoadError(false)
    getProject(slug)
      .then(setProject)
      .catch(() => setProjectLoadError(true))
  }, [slug])

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="page-shell py-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
          <div className="flex items-center gap-4 min-w-0">
            <NavLink to="/" className="text-sm text-gray-500 hover:text-gray-800 shrink-0">
              &larr; Projects
            </NavLink>
            <h1 className="text-lg font-semibold text-gray-900 truncate">{slug}</h1>
          </div>
          {!isClientViewer && <SearchBar />}
          <nav className="flex gap-2 flex-wrap">
            <NavLink to={`/${slug}/dashboard`} className={tabClass}>
              Dashboard
            </NavLink>
            <NavLink to={`/${slug}/functions`} className={tabClass}>
              Functions
            </NavLink>
            <NavLink to={`/${slug}/gantt`} className={tabClass}>
              Gantt
            </NavLink>
            {/* Progress-reporting view, so readable by every role — same
                treatment as the Gantt it sits next to. */}
            <NavLink to={`/${slug}/progress-matrix`} className={tabClass}>
              Matrix
            </NavLink>
            {!isClientViewer && (
              <NavLink to={`/${slug}/tasks`} className={tabClass}>
                Tasks
              </NavLink>
            )}
            <NavLink to={`/${slug}/documents`} className={tabClass}>
              Documents
            </NavLink>
            {!isClientViewer && (
              <NavLink to={`/${slug}/notes`} className={tabClass}>
                Notes
              </NavLink>
            )}
            {/* Notes Hub is readable by every role (writes are blocked
                server-side), unlike the internal-only quick Notes tab. */}
            <NavLink to={`/${slug}/notes-hub`} className={tabClass}>
              Notes Hub
            </NavLink>
            {!isClientViewer && (
              <NavLink to={`/${slug}/allocations`} className={tabClass}>
                Resources
              </NavLink>
            )}
            {!isClientViewer && (
              <NavLink to={`/${slug}/board`} className={tabClass}>
                Board
              </NavLink>
            )}
            {/* Readable by every role — a client is meant to see what a
                change costs before agreeing to it. */}
            <NavLink to={`/${slug}/change-requests`} className={tabClass}>
              Changes
            </NavLink>
            {!isClientViewer && (
              <NavLink to={`/${slug}/whiteboards`} className={tabClass}>
                Whiteboards
              </NavLink>
            )}
            <NavLink to={`/${slug}/reports`} className={tabClass}>
              Reports
            </NavLink>
            {/* Effort & Budget config — the contracted man-days live here. */}
            {user?.role === 'pmo_admin' && (
              <NavLink to={`/${slug}/settings`} className={tabClass}>
                Settings
              </NavLink>
            )}
          </nav>
          <EcosystemStatusIndicator />
          <UserBadge />
        </div>
      </header>
      {projectLoadError && (
        <div className="bg-red-50 border-b border-red-200 text-red-700 text-sm text-center py-2">
          Could not reach the backend to load this project's details. Your data is safe — this page just
          couldn't connect. Try refreshing.
        </div>
      )}
      <main className="page-shell py-6">
        <Outlet context={{ project }} />
      </main>
      <QuickNoteBar />
    </div>
  )
}
