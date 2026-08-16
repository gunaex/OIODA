import { lazy, Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import RequireAuth from './auth/RequireAuth';
import { CardSkeleton, DashboardSkeleton, TableSkeleton } from './components/PageSkeleton';

const LoginPage = lazy(() => import('./pages/LoginPage'));
const ProjectList = lazy(() => import('./pages/ProjectList'));
const ProjectDashboard = lazy(() => import('./pages/ProjectDashboard'));

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={
        <Suspense fallback={<div className="min-h-screen bg-gray-50" />}>
          <LoginPage />
        </Suspense>
      } />

      <Route path="/" element={
        <RequireAuth>
          <Suspense fallback={<CardSkeleton count={3} />}>
            <ProjectList />
          </Suspense>
        </RequireAuth>
      } />

      <Route path="/:slug" element={
        <RequireAuth>
          <Suspense fallback={<DashboardSkeleton />}>
            <ProjectDashboard />
          </Suspense>
        </RequireAuth>
      } />

      <Route path="/:slug/*" element={
        <RequireAuth>
          <Suspense fallback={<DashboardSkeleton />}>
            <ProjectDashboard />
          </Suspense>
        </RequireAuth>
      } />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
