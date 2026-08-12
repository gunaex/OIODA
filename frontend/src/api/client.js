import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

let onUnauthorized = null;

export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401 && onUnauthorized) {
      const url = error.config?.url || '';
      if (!url.includes('/auth/login') && !url.includes('/auth/me')) {
        onUnauthorized();
      }
    }
    return Promise.reject(error);
  },
);

// ── Auth ──────────────────────────────────────────────────
export const login = (email, password) =>
  api.post('/auth/login', { email, password }).then((r) => r.data);

export const logout = () =>
  api.post('/auth/logout').then((r) => r.data);

export const getMe = () =>
  api.get('/auth/me').then((r) => r.data);

export const changePassword = (current_password, new_password) =>
  api.post('/auth/change-password', { current_password, new_password }).then((r) => r.data);

// ── Projects ──────────────────────────────────────────────
export const listProjects = () =>
  api.get('/projects').then((r) => r.data);

export const createProject = (data) =>
  api.post('/projects', data).then((r) => r.data);

export const updateProject = (slug, data) =>
  api.patch(`/projects/${slug}`, data).then((r) => r.data);

// ── Vision ────────────────────────────────────────────────
export const listVisions = (slug) =>
  api.get(`/${slug}/vision`).then((r) => r.data);

export const createVision = (slug, content) =>
  api.post(`/${slug}/vision`, { content }).then((r) => r.data);

// ── Requirements ──────────────────────────────────────────
export const listRequirements = (slug) =>
  api.get(`/${slug}/requirements`).then((r) => r.data);

export const createRequirement = (slug, data) =>
  api.post(`/${slug}/requirements`, data).then((r) => r.data);
