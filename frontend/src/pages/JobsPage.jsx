import { useState, useEffect, useCallback, useRef } from 'react'
import {
  MagnifyingGlassIcon,
  ArrowPathIcon,
  BriefcaseIcon,
  MapPinIcon,
  BuildingOffice2Icon,
  SparklesIcon,
  FunnelIcon,
  ArrowTopRightOnSquareIcon,
} from '@heroicons/react/24/outline'
import { jobsApi, clientsApi, scraperApi } from '../services/api'
import Spinner from '../components/Spinner'

function StatCard({ label, value, highlight }) {
  return (
    <div className={`card p-4 ${highlight ? 'border-brand-200 bg-brand-50' : ''}`}>
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${highlight ? 'text-brand-700' : 'text-gray-900'}`}>{value}</p>
    </div>
  )
}

function JobRow({ job }) {
  const date = new Date(job.found_at)
  const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })

  return (
    <tr className="hover:bg-gray-50 transition-colors group">
      <td className="px-4 py-3">
        <div className="flex items-start gap-2">
          <div>
            {job.job_url ? (
              <a
                href={job.job_url}
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-gray-900 hover:text-brand-600 flex items-center gap-1 group/link"
              >
                {job.title}
                <ArrowTopRightOnSquareIcon className="h-3.5 w-3.5 opacity-0 group-hover/link:opacity-100 transition-opacity flex-shrink-0" />
              </a>
            ) : (
              <span className="font-medium text-gray-900">{job.title}</span>
            )}
            {job.department && (
              <p className="text-xs text-gray-400 mt-0.5">{job.department}</p>
            )}
          </div>
          {job.is_new && (
            <span className="badge-blue flex-shrink-0 mt-0.5">
              <SparklesIcon className="h-3 w-3 mr-0.5" />
              New
            </span>
          )}
        </div>
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1 text-sm text-gray-600">
          <BuildingOffice2Icon className="h-3.5 w-3.5 text-gray-400 flex-shrink-0" />
          {job.client_name}
        </div>
      </td>
      <td className="px-4 py-3">
        {job.location ? (
          <div className="flex items-center gap-1 text-sm text-gray-600">
            <MapPinIcon className="h-3.5 w-3.5 text-gray-400 flex-shrink-0" />
            {job.location}
          </div>
        ) : (
          <span className="text-sm text-gray-400">—</span>
        )}
      </td>
      <td className="px-4 py-3 text-sm text-gray-500 whitespace-nowrap">{dateStr}</td>
    </tr>
  )
}

export default function JobsPage() {
  const [jobs, setJobs] = useState([])
  const [stats, setStats] = useState(null)
  const [clients, setClients] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Filters
  const [keyword, setKeyword] = useState('')
  const [clientFilter, setClientFilter] = useState('')
  const [locationFilter, setLocationFilter] = useState('')
  const [activeOnly, setActiveOnly] = useState(true)

  // Scraping
  const [scrapingAll, setScrapingAll] = useState(false)
  const [scrapeStatus, setScrapeStatus] = useState({})

  const debounceRef = useRef(null)

  const loadJobs = useCallback(async (filters = {}) => {
    setLoading(true)
    try {
      const params = {
        active_only: activeOnly,
        ...(clientFilter && { client_id: parseInt(clientFilter) }),
        ...(locationFilter && { location: locationFilter }),
        ...(keyword && { keyword }),
        ...filters,
      }
      const data = await jobsApi.list(params)
      setJobs(data.jobs)
    } catch {
      setError('Failed to load jobs')
    } finally {
      setLoading(false)
    }
  }, [activeOnly, clientFilter, locationFilter, keyword])

  const loadStats = useCallback(async () => {
    try {
      const s = await jobsApi.stats()
      setStats(s)
    } catch {}
  }, [])

  useEffect(() => {
    clientsApi.list().then(setClients).catch(() => {})
    loadStats()
  }, [loadStats])

  // Debounced filter reload
  useEffect(() => {
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => loadJobs(), 300)
    return () => clearTimeout(debounceRef.current)
  }, [loadJobs])

  // Poll scrape status
  useEffect(() => {
    const poll = async () => {
      try {
        const status = await scraperApi.status()
        setScrapeStatus(status)
        const anyRunning = Object.values(status).some(s => s.running)
        if (!anyRunning && scrapingAll) {
          setScrapingAll(false)
          await loadJobs()
          await loadStats()
        }
      } catch {}
    }
    const id = setInterval(poll, 3000)
    return () => clearInterval(id)
  }, [scrapingAll, loadJobs, loadStats])

  const handleScrapeAll = async () => {
    setScrapingAll(true)
    try {
      await scraperApi.run(null)
    } catch (err) {
      setScrapingAll(false)
      setError('Failed to start scrape: ' + (err.response?.data?.detail || err.message))
    }
  }

  const uniqueLocations = [...new Set(jobs.map(j => j.location).filter(Boolean))].sort()

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Jobs Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">All job listings across active clients</p>
        </div>
        <button
          className="btn-primary btn-sm"
          onClick={handleScrapeAll}
          disabled={scrapingAll}
        >
          {scrapingAll ? <Spinner className="h-4 w-4" /> : <ArrowPathIcon className="h-4 w-4" />}
          {scrapingAll ? 'Scraping...' : 'Scrape All'}
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 gap-4">
          <StatCard label="Total Active Jobs" value={stats.total_active} />
          <StatCard label="New (last 48h)" value={stats.new_last_48h} highlight />
        </div>
      )}

      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700 flex items-center justify-between">
          {error}
          <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700">×</button>
        </div>
      )}

      {/* Filters */}
      <div className="card p-4">
        <div className="flex items-center gap-2 mb-3">
          <FunnelIcon className="h-4 w-4 text-gray-400" />
          <span className="text-sm font-medium text-gray-700">Filters</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="relative">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              className="input pl-9"
              placeholder="Search jobs..."
              value={keyword}
              onChange={e => setKeyword(e.target.value)}
            />
          </div>

          <select
            className="input"
            value={clientFilter}
            onChange={e => setClientFilter(e.target.value)}
          >
            <option value="">All Clients</option>
            {clients.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>

          <input
            className="input"
            placeholder="Filter by location..."
            value={locationFilter}
            onChange={e => setLocationFilter(e.target.value)}
          />

          <div className="flex items-center gap-2">
            <input
              id="active_only"
              type="checkbox"
              className="h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
              checked={activeOnly}
              onChange={e => setActiveOnly(e.target.checked)}
            />
            <label htmlFor="active_only" className="text-sm text-gray-700">Active jobs only</label>
          </div>
        </div>
      </div>

      {/* Jobs table */}
      <div className="card overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-48">
            <Spinner className="h-8 w-8 text-brand-600" />
          </div>
        ) : jobs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-center px-4">
            <BriefcaseIcon className="h-10 w-10 text-gray-300 mb-3" />
            <p className="text-gray-500 text-sm font-medium">No jobs found</p>
            <p className="text-gray-400 text-xs mt-1">
              {clients.length === 0
                ? 'Add clients first, then run a scrape to find jobs.'
                : 'Try adjusting your filters or run a scrape to fetch the latest jobs.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    Job Title
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    Client
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    Location
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                    Date Found
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-100">
                {jobs.map(job => <JobRow key={job.id} job={job} />)}
              </tbody>
            </table>
            <div className="px-4 py-3 bg-gray-50 border-t border-gray-200 text-xs text-gray-500">
              Showing {jobs.length} job{jobs.length !== 1 ? 's' : ''}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
