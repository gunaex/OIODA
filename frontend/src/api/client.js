import axios from 'axios'

// Local dev: VITE_API_BASE_URL is unset, so this resolves to '/api' — the
// Vite dev server proxy (see vite.config.js) handles it. Production
// (Cloudflare Pages): set VITE_API_BASE_URL to the deployed backend's
// origin (e.g. https://api.qaagain.kanphong.com) so the built frontend
// calls it directly — a cross-origin call, which is why the backend's
// ALLOWED_ORIGINS needs to include the frontend's origin.
const API_BASE = `${import.meta.env.VITE_API_BASE_URL || ''}/api`

// withCredentials: true is required so the httpOnly auth cookies the
// backend sets on login are actually sent back on every request — without
// it every request is anonymous and gets 401.
const api = axios.create({ baseURL: API_BASE, withCredentials: true })

// Registered by AuthProvider so a 401 from any call (session expired,
// cookie cleared) can clear the in-memory user and bounce to /login.
// Login failures (wrong password) and the initial /auth/me probe are
// expected to 401 sometimes and must not trigger this.
let onUnauthorized = null
export const setUnauthorizedHandler = (fn) => {
  onUnauthorized = fn
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = error.config?.url || ''
    if (error.response?.status === 401 && !url.includes('/auth/login') && !url.includes('/auth/me')) {
      onUnauthorized?.()
    }
    return Promise.reject(error)
  },
)

// Auth
export const login = (email, password) => api.post('/auth/login', { email, password }).then((r) => r.data)
export const logout = () => api.post('/auth/logout').then((r) => r.data)
export const getMe = () => api.get('/auth/me').then((r) => r.data)
export const changePassword = (currentPassword, newPassword) =>
  api
    .post('/auth/change-password', { current_password: currentPassword, new_password: newPassword })
    .then((r) => r.data)

// Projects
export const listProjects = (includeArchived = false) =>
  api.get('/projects', { params: { include_archived: includeArchived } }).then((r) => r.data)
export const createProject = (name, externalProjectUrl = null) =>
  api.post('/projects', { name, external_project_url: externalProjectUrl }).then((r) => r.data)
export const getProject = (slug) => api.get(`/projects/${slug}`).then((r) => r.data)
export const archiveProject = (slug, archived, password) =>
  api.put(`/projects/${slug}/archive`, { archived, password }).then((r) => r.data)
export const deleteProject = (slug, password) =>
  api.delete(`/projects/${slug}`, { data: { password } }).then((r) => r.data)

export default api
