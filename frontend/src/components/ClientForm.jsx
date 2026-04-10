import { useState, useEffect } from 'react'
import { clientsApi } from '../services/api'
import Spinner from './Spinner'

const EMPTY = {
  name: '',
  career_url: '',
  ats_platform: '',
  city: '',
  notes: '',
  is_active: true,
}

export default function ClientForm({ initial, onSave, onCancel }) {
  const [form, setForm] = useState(initial ? { ...EMPTY, ...initial, ats_platform: initial.ats_platform || '' } : EMPTY)
  const [platforms, setPlatforms] = useState([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    clientsApi.atsPlatforms().then(setPlatforms).catch(() => {})
  }, [])

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      const payload = {
        ...form,
        ats_platform: form.ats_platform || null,
        city: form.city || null,
        notes: form.notes || null,
      }
      let result
      if (initial?.id) {
        result = await clientsApi.update(initial.id, payload)
      } else {
        result = await clientsApi.create(payload)
      }
      onSave(result)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save client')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700">{error}</div>
      )}

      <div>
        <label className="label">Company Name <span className="text-red-500">*</span></label>
        <input
          className="input"
          value={form.name}
          onChange={e => set('name', e.target.value)}
          placeholder="Acme Corp"
          required
        />
      </div>

      <div>
        <label className="label">Careers URL <span className="text-red-500">*</span></label>
        <input
          className="input"
          type="url"
          value={form.career_url}
          onChange={e => set('career_url', e.target.value)}
          placeholder="https://acme.com/careers"
          required
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="label">ATS Platform</label>
          <select
            className="input"
            value={form.ats_platform}
            onChange={e => set('ats_platform', e.target.value)}
          >
            <option value="">— Select —</option>
            {platforms.map(p => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="label">City</label>
          <input
            className="input"
            value={form.city}
            onChange={e => set('city', e.target.value)}
            placeholder="San Francisco"
          />
        </div>
      </div>

      <div>
        <label className="label">Notes</label>
        <textarea
          className="input resize-none"
          rows={3}
          value={form.notes}
          onChange={e => set('notes', e.target.value)}
          placeholder="Internal notes about this client..."
        />
      </div>

      <div className="flex items-center gap-2">
        <input
          id="is_active"
          type="checkbox"
          className="h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
          checked={form.is_active}
          onChange={e => set('is_active', e.target.checked)}
        />
        <label htmlFor="is_active" className="text-sm text-gray-700">Active (include in scraping)</label>
      </div>

      <div className="flex justify-end gap-3 pt-2 border-t border-gray-100">
        <button type="button" className="btn-secondary" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn-primary" disabled={saving}>
          {saving && <Spinner className="h-4 w-4" />}
          {initial?.id ? 'Save Changes' : 'Add Client'}
        </button>
      </div>
    </form>
  )
}
