const API_BASE = import.meta.env.VITE_API_URL || '/api';

export function getToken() {
  return localStorage.getItem('cx_admin_token');
}

export function setToken(token) {
  localStorage.setItem('cx_admin_token', token);
}

export function clearToken() {
  localStorage.removeItem('cx_admin_token');
}

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json';
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || err.message || 'Request failed');
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  login: (email, password) =>
    request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  seedAdmin: () => request('/auth/seed-admin', { method: 'POST' }),
  listClients: () => request('/admin/clients'),
  createClient: (data) => request('/admin/clients', { method: 'POST', body: JSON.stringify(data) }),
  getClient: (id) => request(`/admin/clients/${id}`),
  deleteClient: (id) => request(`/admin/clients/${id}`, { method: 'DELETE' }),
  listSources: (clientId) => request(`/admin/clients/${clientId}/sources`),
  addUrl: (clientId, data) =>
    request(`/admin/clients/${clientId}/sources/url`, { method: 'POST', body: JSON.stringify(data) }),
  uploadDoc: (clientId, formData) =>
    request(`/admin/clients/${clientId}/sources/upload`, { method: 'POST', body: formData, headers: {} }),
  deleteSource: (clientId, sourceId) =>
    request(`/admin/clients/${clientId}/sources/${sourceId}`, { method: 'DELETE' }),
  retrainSource: (clientId, sourceId) =>
    request(`/admin/clients/${clientId}/sources/${sourceId}/retrain`, { method: 'POST' }),
  listJobs: (clientId) => request(`/admin/clients/${clientId}/jobs`),
  getAgentConfig: (clientId) => request(`/admin/clients/${clientId}/agent-config`),
  updateAgentConfig: (clientId, data) =>
    request(`/admin/clients/${clientId}/agent-config`, { method: 'PUT', body: JSON.stringify(data) }),
  listDomains: (clientId) => request(`/admin/clients/${clientId}/domains`),
  addDomain: (clientId, domain) =>
    request(`/admin/clients/${clientId}/domains`, { method: 'POST', body: JSON.stringify({ domain }) }),
  removeDomain: (clientId, domainId) =>
    request(`/admin/clients/${clientId}/domains/${domainId}`, { method: 'DELETE' }),
  updateWidgetConfig: (clientId, data) =>
    request(`/admin/clients/${clientId}/widget-config`, { method: 'PUT', body: JSON.stringify(data) }),
};
