import axios from 'axios'

// Local dev: VITE_API_BASE_URL is unset, so this resolves to '/api' —
// the same relative path the Vite dev server proxy has always handled
// (see vite.config.js), unchanged from before.
// Production (e.g. Vercel): set VITE_API_BASE_URL to the deployed
// backend's origin (e.g. https://your-backend.fly.dev) so the built
// frontend calls it directly. That's a cross-origin call, which is why
// the backend's ALLOWED_ORIGINS needs to include the frontend's origin.
const API_BASE = `${import.meta.env.VITE_API_BASE_URL || ''}/api`

// withCredentials: true is required so the httpOnly auth cookies the
// backend sets on login are actually sent back on every request (and so
// Set-Cookie from /auth/login and /auth/refresh is honored in the first
// place) — without it every request is anonymous and gets 401.
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
export const createProject = (name, projectType = 'simple', projectCategory = null) =>
  api
    .post('/projects', { name, project_type: projectType, project_category: projectCategory })
    .then((r) => r.data)
export const getProject = (slug) => api.get(`/projects/${slug}`).then((r) => r.data)
export const archiveProject = (slug, archived, password) =>
  api.put(`/projects/${slug}/archive`, { archived, password }).then((r) => r.data)
export const deleteProject = (slug, password) =>
  api.delete(`/projects/${slug}`, { data: { password } }).then((r) => r.data)

// Generic per-entity helpers, entity = 'functions' | 'tasks' | 'gantt'
export const listItems = (slug, entity) => api.get(`/${slug}/${entity}`).then((r) => r.data)
export const createItem = (slug, entity, payload) =>
  api.post(`/${slug}/${entity}`, payload).then((r) => r.data)
export const updateItem = (slug, entity, id, payload) =>
  api.put(`/${slug}/${entity}/${id}`, payload).then((r) => r.data)
export const deleteItem = (slug, entity, id) =>
  api.delete(`/${slug}/${entity}/${id}`).then((r) => r.data)
export const cloneItem = (slug, entity, id) =>
  api.post(`/${slug}/${entity}/${id}/clone`).then((r) => r.data)

export const importTemplateUrl = (slug, entity) => `${API_BASE}/${slug}/${entity}/import-template`
export const exportUrl = (slug, entity) => `${API_BASE}/${slug}/${entity}/export`

export const importItems = (slug, entity, file) => {
  const form = new FormData()
  form.append('file', file)
  return api.post(`/${slug}/${entity}/import`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// Documents
export const getDocument = (slug, id) => api.get(`/${slug}/documents/${id}`).then((r) => r.data)
export const submitDocumentForReview = (slug, id) =>
  api.post(`/${slug}/documents/${id}/submit-review`).then((r) => r.data)
export const signoffDocument = (slug, id, payload) =>
  api.post(`/${slug}/documents/${id}/signoff`, payload).then((r) => r.data)
export const listSignoffs = (slug, id) => api.get(`/${slug}/documents/${id}/signoffs`).then((r) => r.data)
export const uploadDocumentFile = (slug, id, file) => {
  const form = new FormData()
  form.append('file', file)
  return api
    .post(`/${slug}/documents/upload/${id}`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    .then((r) => r.data)
}
export const listSuggestedDocuments = (slug) => api.get(`/${slug}/documents/suggested`).then((r) => r.data)
export const addDocumentFromTemplate = (slug, docCode) =>
  api.post(`/${slug}/documents/from-template/${docCode}`).then((r) => r.data)

// Search
export const search = (slug, q) => api.get(`/${slug}/search`, { params: { q } }).then((r) => r.data)

// Comments
export const listComments = (slug, entityType, entityId) =>
  api.get(`/${slug}/comments`, { params: { entity_type: entityType, entity_id: entityId } }).then((r) => r.data)
export const createComment = (slug, entityType, entityId, content, createdBy) =>
  api
    .post(`/${slug}/comments`, { entity_type: entityType, entity_id: entityId, content, created_by: createdBy })
    .then((r) => r.data)
export const deleteComment = (slug, id) => api.delete(`/${slug}/comments/${id}`).then((r) => r.data)

// Activity log
export const listActivity = (slug, entityType, entityId) =>
  api.get(`/${slug}/activity`, { params: { entity_type: entityType, entity_id: entityId } }).then((r) => r.data)

// Notes
export const listNotes = (slug, status) => api.get(`/${slug}/notes`, { params: { status } }).then((r) => r.data)
export const createNote = (slug, content) => api.post(`/${slug}/notes`, { content }).then((r) => r.data)
export const deleteNote = (slug, id) => api.delete(`/${slug}/notes/${id}`).then((r) => r.data)
export const promoteNoteToTask = (slug, id) => api.post(`/${slug}/notes/${id}/promote-task`).then((r) => r.data)
export const promoteNoteToIssue = (slug, id) => api.post(`/${slug}/notes/${id}/promote-issue`).then((r) => r.data)

// Board Items (Issue / Incident / Backlog)
export const listBoardItems = (slug, type, filters = {}) =>
  api.get(`/${slug}/board-items`, { params: { type, ...filters } }).then((r) => r.data)
export const createBoardItem = (slug, payload) =>
  api.post(`/${slug}/board-items`, payload).then((r) => r.data)
export const updateBoardItem = (slug, id, payload) =>
  api.put(`/${slug}/board-items/${id}`, payload).then((r) => r.data)
export const deleteBoardItem = (slug, id) => api.delete(`/${slug}/board-items/${id}`).then((r) => r.data)
export const promoteBoardItem = (slug, id, targetType) =>
  api.post(`/${slug}/board-items/${id}/promote`, { target_type: targetType }).then((r) => r.data)
export const boardExportUrl = (slug, type) => `${API_BASE}/${slug}/board-items/export?type=${type}`

// Reports
export const reportUrl = (slug, type, params = {}) => {
  const qs = new URLSearchParams(params).toString()
  return `${API_BASE}/${slug}/reports/${type}${qs ? `?${qs}` : ''}`
}

// Whiteboards
export const listWhiteboards = (slug, linkedEntityType, linkedEntityId) =>
  api
    .get(`/${slug}/whiteboards`, {
      params: { linked_entity_type: linkedEntityType, linked_entity_id: linkedEntityId },
    })
    .then((r) => r.data)
export const getWhiteboard = (slug, id) => api.get(`/${slug}/whiteboards/${id}`).then((r) => r.data)
export const createWhiteboard = (slug, payload) =>
  api.post(`/${slug}/whiteboards`, payload).then((r) => r.data)
export const updateWhiteboard = (slug, id, payload) =>
  api.put(`/${slug}/whiteboards/${id}`, payload).then((r) => r.data)
export const deleteWhiteboard = (slug, id) => api.delete(`/${slug}/whiteboards/${id}`).then((r) => r.data)

// Auto-Diagram Generators
export const generateErdDiagram = (slug) => api.get(`/${slug}/diagrams/erd`).then((r) => r.data)
export const generateDocumentWorkflowDiagram = (slug) =>
  api.get(`/${slug}/diagrams/workflow/document-status`).then((r) => r.data)
export const generateBoardItemWorkflowDiagram = (slug) =>
  api.get(`/${slug}/diagrams/workflow/board-item-promote`).then((r) => r.data)

// Gantt Annotations
export const listGanttAnnotations = (slug) => api.get(`/${slug}/gantt-annotations`).then((r) => r.data)
export const createGanttAnnotation = (slug, payload) =>
  api.post(`/${slug}/gantt-annotations`, payload).then((r) => r.data)
export const updateGanttAnnotation = (slug, id, payload) =>
  api.put(`/${slug}/gantt-annotations/${id}`, payload).then((r) => r.data)
export const deleteGanttAnnotation = (slug, id) =>
  api.delete(`/${slug}/gantt-annotations/${id}`).then((r) => r.data)

// Resources (global — not tied to a project slug)
export const listResources = () => api.get('/resources').then((r) => r.data)
export const createResource = (payload) => api.post('/resources', payload).then((r) => r.data)
export const updateResource = (id, payload) => api.put(`/resources/${id}`, payload).then((r) => r.data)
export const deleteResource = (id) => api.delete(`/resources/${id}`).then((r) => r.data)
export const getResourceUtilization = (from, to) =>
  api.get('/resources/utilization', { params: { from, to } }).then((r) => r.data)

// Resource Allocations (per-project, but backed by the global resource pool)
export const listAllocations = (slug) => api.get(`/${slug}/resource-allocations`).then((r) => r.data)
export const createAllocation = (slug, payload) =>
  api.post(`/${slug}/resource-allocations`, payload).then((r) => r.data)
export const updateAllocation = (slug, id, payload) =>
  api.put(`/${slug}/resource-allocations/${id}`, payload).then((r) => r.data)
export const deleteAllocation = (slug, id) => api.delete(`/${slug}/resource-allocations/${id}`).then((r) => r.data)

// Dashboards
export const getProjectDashboard = (slug) => api.get(`/${slug}/dashboard`).then((r) => r.data)
export const getGlobalDashboard = () => api.get('/dashboard/global').then((r) => r.data)

// Slippage Predictor
export const getSlippageSummary = (slug) => api.get(`/${slug}/slippage/summary`).then((r) => r.data)

// Thai Holidays (global, pmo_admin-managed)
export const listHolidays = (year) => api.get('/holidays', { params: { year } }).then((r) => r.data)
export const createHoliday = (payload) => api.post('/holidays', payload).then((r) => r.data)
export const updateHoliday = (id, payload) => api.put(`/holidays/${id}`, payload).then((r) => r.data)
export const deleteHoliday = (id) => api.delete(`/holidays/${id}`).then((r) => r.data)
export const addBusinessDays = (start, days) =>
  api.get('/business-days/add', { params: { start, days } }).then((r) => r.data.result_date)

// Get-or-create: used by "Open/Create Whiteboard" entry points on other
// pages. Returns the id of the (first) whiteboard already linked to this
// entity, or creates a new one if none exists yet.
export const openOrCreateWhiteboard = async (slug, entityType, entityId, title) => {
  const existing = await listWhiteboards(slug, entityType, entityId)
  if (existing.length > 0) return existing[0].id
  const created = await createWhiteboard(slug, {
    title,
    linked_entity_type: entityType,
    linked_entity_id: entityId,
  })
  return created.id
}

export default api
