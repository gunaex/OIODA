import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import ProjectList from './pages/ProjectList.jsx'
import ProjectDashboard from './pages/ProjectDashboard.jsx'
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
      </Route>
    </Routes>
  )
}

export default App
