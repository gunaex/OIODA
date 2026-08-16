import { Suspense, lazy } from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import ProjectList from './pages/ProjectList.jsx'
import FunctionList from './pages/FunctionList.jsx'
import GanttView from './pages/GanttView.jsx'
import TaskList from './pages/TaskList.jsx'
import DocumentList from './pages/DocumentList.jsx'
import DocumentDetail from './pages/DocumentDetail.jsx'
import NoteList from './pages/NoteList.jsx'
// Lazy: the Notes Hub is the only page that pulls in the markdown editor,
// which is a big dependency — no reason to ship it to someone who only opens
// the Gantt chart.
const NotesHub = lazy(() => import('./pages/NotesHub.jsx'))
import ReportsPage from './pages/ReportsPage.jsx'
import BoardPage from './pages/BoardPage.jsx'
import WhiteboardList from './pages/WhiteboardList.jsx'
import WhiteboardEditor from './pages/WhiteboardEditor.jsx'
import LoginPage from './pages/LoginPage.jsx'
import ResourcePool from './pages/ResourcePool.jsx'
import ProjectAllocations from './pages/ProjectAllocations.jsx'
import ProjectDashboard from './pages/ProjectDashboard.jsx'
import ProgressMatrix from './pages/ProgressMatrix.jsx'
import ChangeRequestPage from './pages/ChangeRequestPage.jsx'
import ProjectSettings from './pages/ProjectSettings.jsx'
import HolidaysAdmin from './pages/HolidaysAdmin.jsx'
import RequireAuth from './auth/RequireAuth.jsx'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <ProjectList />
          </RequireAuth>
        }
      />
      <Route
        path="/resources"
        element={
          <RequireAuth>
            <ResourcePool />
          </RequireAuth>
        }
      />
      <Route
        path="/holidays"
        element={
          <RequireAuth>
            <HolidaysAdmin />
          </RequireAuth>
        }
      />
      <Route
        path="/:slug"
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<ProjectDashboard />} />
        <Route path="dashboard" element={<ProjectDashboard />} />
        <Route path="functions" element={<FunctionList />} />
        <Route path="gantt" element={<GanttView />} />
        <Route path="progress-matrix" element={<ProgressMatrix />} />
        <Route path="change-requests" element={<ChangeRequestPage />} />
        <Route path="settings" element={<ProjectSettings />} />
        <Route path="tasks" element={<TaskList />} />
        <Route path="documents" element={<DocumentList />} />
        <Route path="documents/:id" element={<DocumentDetail />} />
        <Route path="notes" element={<NoteList />} />
        <Route
          path="notes-hub"
          element={
            <Suspense fallback={<p className="text-gray-400 text-sm">Loading…</p>}>
              <NotesHub />
            </Suspense>
          }
        />
        <Route path="allocations" element={<ProjectAllocations />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="board" element={<BoardPage />} />
        <Route path="whiteboards" element={<WhiteboardList />} />
        <Route path="whiteboards/:id" element={<WhiteboardEditor />} />
      </Route>
    </Routes>
  )
}

export default App
