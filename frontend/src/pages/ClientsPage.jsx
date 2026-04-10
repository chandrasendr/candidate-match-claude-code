import { useState, useEffect, useRef, useCallback } from 'react'
import {
  PlusIcon,
  PencilSquareIcon,
  TrashIcon,
  ArrowUpTrayIcon,
  ArrowPathIcon,
  BuildingOffice2Icon,
  CheckCircleIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline'
import { clientsApi, scraperApi } from '../services/api'
import Modal from '../components/Modal'
import ClientForm from '../components/ClientForm'
import ConfirmDialog from '../components/ConfirmDialog'
import Spinner from '../components/Spinner'

function ScrapeStatusBadge({ status }) {
  if (!status) return null
  if (status.running) return <span className="badge-yellow">Scraping...</span>
  return null
}

export default function ClientsPage() {
  const [clients, setClients] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Modal states
  const [showForm, setShowForm] = useState(false)
  const [editClient, setEditClient] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [showImport, setShowImport] = useState(false)

  // Scraping state
  const [scrapeStatus, setScrapeStatus] = useState({}) // { clientId: { running, error } }
  const [scrapingAll, setScrapingAll] = useState(false)

  // CSV import
  const [csvFile, setCsvFile] = useState(null)
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState(null)
  const fileRef = useRef(null)

  const loadClients = useCallback(async () => {
    try {
      const data = await clientsApi.list()
      setClients(data)
    } catch {
      setError('Failed to load clients')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadClients() }, [loadClients])

  // Poll scrape status
  useEffect(() => {
    const poll = async () => {
      try {
        const status = await scraperApi.status()
        setScrapeStatus(status)
        const anyRunning = Object.values(status).some(s => s.running)
        setScrapingAll(prev => {
          if (prev && !anyRunning) { loadClients(); return false }
          return anyRunning && prev
        })
      } catch {}
    }
    const id = setInterval(poll, 3000)
    return () => clearInterval(id)
  }, [loadClients])

  const handleSave = (client) => {
    setShowForm(false)
    setEditClient(null)
    setClients(prev => {
      const idx = prev.findIndex(c => c.id === client.id)
      if (idx >= 0) {
        const next = [...prev]
        next[idx] = client
        return next
      }
      return [...prev, client].sort((a, b) => a.name.localeCompare(b.name))
    })
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await clientsApi.delete(deleteTarget.id)
      setClients(prev => prev.filter(c => c.id !== deleteTarget.id))
    } catch {
      setError('Failed to delete client')
    } finally {
      setDeleteTarget(null)
    }
  }

  const handleScrapeClient = async (client) => {
    try {
      setScrapeStatus(prev => ({ ...prev, [client.id]: { running: true } }))
      await scraperApi.run([client.id])
    } catch (err) {
      setScrapeStatus(prev => ({ ...prev, [client.id]: { running: false, error: err.message } }))
    }
  }

  const handleScrapeAll = async () => {
    setScrapingAll(true)
    try {
      await scraperApi.run(null)
    } catch (err) {
      setScrapingAll(false)
      setError('Failed to start scrape: ' + (err.response?.data?.detail || err.message))
    }
  }

  const handleImport = async () => {
    if (!csvFile) return
    setImporting(true)
    setImportResult(null)
    try {
      const result = await clientsApi.importCsv(csvFile)
      setImportResult(result)
      await loadClients()
    } catch (err) {
      setImportResult({ error: err.response?.data?.detail || 'Import failed' })
    } finally {
      setImporting(false)
      setCsvFile(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner className="h-8 w-8 text-brand-600" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Clients</h1>
          <p className="text-sm text-gray-500 mt-0.5">{clients.length} client{clients.length !== 1 ? 's' : ''}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="btn-secondary btn-sm"
            onClick={() => setShowImport(true)}
          >
            <ArrowUpTrayIcon className="h-4 w-4" />
            Import CSV
          </button>
          <button
            className="btn-secondary btn-sm"
            onClick={handleScrapeAll}
            disabled={scrapingAll}
          >
            {scrapingAll ? <Spinner className="h-4 w-4" /> : <ArrowPathIcon className="h-4 w-4" />}
            Scrape All
          </button>
          <button
            className="btn-primary btn-sm"
            onClick={() => { setEditClient(null); setShowForm(true) }}
          >
            <PlusIcon className="h-4 w-4" />
            Add Client
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700 flex items-center justify-between">
          {error}
          <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700">×</button>
        </div>
      )}

      {/* Client grid */}
      {clients.length === 0 ? (
        <div className="card p-12 text-center">
          <BuildingOffice2Icon className="h-12 w-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500 text-sm">No clients yet. Add your first client to get started.</p>
          <button className="btn-primary mt-4" onClick={() => setShowForm(true)}>
            <PlusIcon className="h-4 w-4" />
            Add Client
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {clients.map(client => {
            const cs = scrapeStatus[client.id] || scrapeStatus['all']
            const isRunning = cs?.running

            return (
              <div key={client.id} className="card p-4 flex flex-col gap-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-semibold text-gray-900 truncate">{client.name}</h3>
                      {client.is_active ? (
                        <span className="badge-green">Active</span>
                      ) : (
                        <span className="badge-gray">Inactive</span>
                      )}
                    </div>
                    {client.city && (
                      <p className="text-xs text-gray-500 mt-0.5">{client.city}</p>
                    )}
                  </div>
                  {client.ats_platform && (
                    <span className="badge-blue flex-shrink-0">{client.ats_platform}</span>
                  )}
                </div>

                <a
                  href={client.career_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-brand-600 hover:text-brand-700 truncate block"
                >
                  {client.career_url}
                </a>

                {client.notes && (
                  <p className="text-xs text-gray-500 line-clamp-2">{client.notes}</p>
                )}

                <div className="flex items-center gap-2 pt-2 border-t border-gray-100">
                  <button
                    className="btn-secondary btn-sm flex-1"
                    onClick={() => handleScrapeClient(client)}
                    disabled={isRunning || !client.is_active}
                  >
                    {isRunning ? <Spinner className="h-3.5 w-3.5" /> : <ArrowPathIcon className="h-3.5 w-3.5" />}
                    Scrape
                  </button>
                  <button
                    className="btn-secondary btn-sm"
                    onClick={() => { setEditClient(client); setShowForm(true) }}
                  >
                    <PencilSquareIcon className="h-3.5 w-3.5" />
                  </button>
                  <button
                    className="btn-danger btn-sm"
                    onClick={() => setDeleteTarget(client)}
                  >
                    <TrashIcon className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Add/Edit modal */}
      <Modal
        open={showForm}
        onClose={() => { setShowForm(false); setEditClient(null) }}
        title={editClient ? `Edit ${editClient.name}` : 'Add New Client'}
      >
        <ClientForm
          initial={editClient}
          onSave={handleSave}
          onCancel={() => { setShowForm(false); setEditClient(null) }}
        />
      </Modal>

      {/* Delete confirm */}
      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete Client"
        message={`Are you sure you want to delete "${deleteTarget?.name}"? This will also remove all scraped jobs for this client.`}
        dangerous
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />

      {/* CSV Import modal */}
      <Modal
        open={showImport}
        onClose={() => { setShowImport(false); setCsvFile(null); setImportResult(null) }}
        title="Import Clients from CSV"
        size="sm"
      >
        <div className="space-y-4">
          <p className="text-sm text-gray-600">
            Upload a CSV with columns: <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">name</code>,{' '}
            <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">career_url</code>{' '}
            (optional: <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">ats_platform</code>,{' '}
            <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">city</code>,{' '}
            <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">notes</code>,{' '}
            <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">is_active</code>)
          </p>

          <div
            className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center cursor-pointer hover:border-brand-400 transition-colors"
            onClick={() => fileRef.current?.click()}
          >
            <ArrowUpTrayIcon className="h-8 w-8 text-gray-400 mx-auto mb-2" />
            {csvFile ? (
              <p className="text-sm text-gray-700 font-medium">{csvFile.name}</p>
            ) : (
              <p className="text-sm text-gray-500">Click to select a CSV file</p>
            )}
            <input
              ref={fileRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={e => { setCsvFile(e.target.files[0]); setImportResult(null) }}
            />
          </div>

          {importResult && (
            <div className={`rounded-md p-3 text-sm ${importResult.error ? 'bg-red-50 border border-red-200 text-red-700' : 'bg-green-50 border border-green-200 text-green-700'}`}>
              {importResult.error ? (
                importResult.error
              ) : (
                <>
                  <p className="font-medium">Import complete</p>
                  <p>Created: {importResult.created} • Skipped: {importResult.skipped}</p>
                  {importResult.errors?.length > 0 && (
                    <ul className="mt-1 list-disc list-inside text-xs">
                      {importResult.errors.map((e, i) => <li key={i}>{e}</li>)}
                    </ul>
                  )}
                </>
              )}
            </div>
          )}

          <div className="flex justify-end gap-3">
            <button className="btn-secondary" onClick={() => { setShowImport(false); setCsvFile(null); setImportResult(null) }}>
              Close
            </button>
            <button
              className="btn-primary"
              disabled={!csvFile || importing}
              onClick={handleImport}
            >
              {importing && <Spinner className="h-4 w-4" />}
              Import
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
