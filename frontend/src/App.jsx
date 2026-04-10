import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom'
import { BuildingOffice2Icon, BriefcaseIcon } from '@heroicons/react/24/outline'
import ClientsPage from './pages/ClientsPage'
import JobsPage from './pages/JobsPage'

function Navbar() {
  const linkClass = ({ isActive }) =>
    `flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
      isActive
        ? 'bg-brand-600 text-white'
        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
    }`

  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          <div className="flex items-center gap-8">
            <span className="text-lg font-bold text-brand-600 tracking-tight">
              CandidateMatch
            </span>
            <nav className="flex items-center gap-1">
              <NavLink to="/clients" className={linkClass}>
                <BuildingOffice2Icon className="h-4 w-4" />
                Clients
              </NavLink>
              <NavLink to="/jobs" className={linkClass}>
                <BriefcaseIcon className="h-4 w-4" />
                Jobs
              </NavLink>
            </nav>
          </div>
        </div>
      </div>
    </header>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen flex flex-col">
        <Navbar />
        <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-6">
          <Routes>
            <Route path="/" element={<Navigate to="/jobs" replace />} />
            <Route path="/clients" element={<ClientsPage />} />
            <Route path="/jobs" element={<JobsPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
