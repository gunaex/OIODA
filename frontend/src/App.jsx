import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import ProjectList from './pages/ProjectList.jsx'
import ProjectDashboard from './pages/ProjectDashboard.jsx'
import SuiteList from './pages/SuiteList.jsx'
import SuiteDetail from './pages/SuiteDetail.jsx'
import RevisionDetail from './pages/RevisionDetail.jsx'
import LoginPage from './pages/LoginPage.jsx'
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
        path="/:slug"
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<ProjectDashboard />} />
        <Route path="dashboard" element={<ProjectDashboard />} />
        <Route path="suites" element={<SuiteList />} />
        <Route path="suites/:suiteId" element={<SuiteDetail />} />
        <Route path="suites/:suiteId/revisions/:revisionId" element={<RevisionDetail />} />
      </Route>
    </Routes>
  )
}

export default App
