import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

// ── Clients ──────────────────────────────────────────────────────────────────

export const clientsApi = {
  list: (activeOnly = false) =>
    api.get('/clients/', { params: { active_only: activeOnly } }).then(r => r.data),

  get: (id) => api.get(`/clients/${id}`).then(r => r.data),

  create: (data) => api.post('/clients/', data).then(r => r.data),

  update: (id, data) => api.put(`/clients/${id}`, data).then(r => r.data),

  delete: (id) => api.delete(`/clients/${id}`),

  importCsv: (file) => {
    const form = new FormData()
    form.append('file', file)
    return api.post('/clients/import/csv', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data)
  },

  atsPlatforms: () => api.get('/clients/ats-platforms').then(r => r.data.platforms),
}

// ── Jobs ─────────────────────────────────────────────────────────────────────

export const jobsApi = {
  list: (params = {}) => api.get('/jobs/', { params }).then(r => r.data),
  stats: () => api.get('/jobs/stats').then(r => r.data),
}

// ── Scraper ───────────────────────────────────────────────────────────────────

export const scraperApi = {
  run: (clientIds = null) =>
    api.post('/scraper/run', { client_ids: clientIds }).then(r => r.data),

  status: () => api.get('/scraper/status').then(r => r.data),

  logs: (clientId = null, limit = 50) =>
    api.get('/scraper/logs', { params: { client_id: clientId, limit } }).then(r => r.data),
}
