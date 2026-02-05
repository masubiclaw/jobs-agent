import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { jobsApi } from '../api'
import { JobStatus } from '../types'
import { Briefcase, Search, Filter, Plus, ExternalLink } from 'lucide-react'

export default function JobsPage() {
  const [page, setPage] = useState(1)
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<JobStatus | ''>('')
  const [searchInput, setSearchInput] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['jobs', { page, query, status }],
    queryFn: () =>
      jobsApi.list({
        page,
        page_size: 20,
        query: query || undefined,
        status: status || undefined,
      }),
  })

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setQuery(searchInput)
    setPage(1)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Jobs</h1>
          <p className="text-gray-600 mt-1">
            Browse and manage job listings
          </p>
        </div>
        <Link to="/jobs/add" className="btn btn-primary flex items-center gap-2">
          <Plus size={20} />
          Add Job
        </Link>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex flex-col sm:flex-row gap-4">
          <form onSubmit={handleSearch} className="flex-1 flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={20} />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search jobs..."
                className="input pl-10"
              />
            </div>
            <button type="submit" className="btn btn-secondary">
              Search
            </button>
          </form>

          <div className="flex items-center gap-2">
            <Filter size={20} className="text-gray-400" />
            <select
              value={status}
              onChange={(e) => {
                setStatus(e.target.value as JobStatus | '')
                setPage(1)
              }}
              className="input w-40"
            >
              <option value="">All Status</option>
              <option value="active">Active</option>
              <option value="completed">Completed</option>
              <option value="archived">Archived</option>
            </select>
          </div>
        </div>
      </div>

      {/* Job list */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      ) : data && data.jobs.length > 0 ? (
        <>
          <div className="space-y-4">
            {data.jobs.map((job) => (
              <div key={job.id} className="card hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <Link
                        to={`/jobs/${job.id}`}
                        className="text-lg font-semibold text-gray-900 hover:text-primary-600"
                      >
                        {job.title}
                      </Link>
                      {job.match && (
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          job.match.combined_score >= 80
                            ? 'bg-green-100 text-green-700'
                            : job.match.combined_score >= 60
                            ? 'bg-yellow-100 text-yellow-700'
                            : 'bg-gray-100 text-gray-700'
                        }`}>
                          {job.match.combined_score}% match
                        </span>
                      )}
                    </div>
                    <p className="text-gray-600">{job.company}</p>
                    <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
                      <span>{job.location}</span>
                      {job.salary && job.salary !== 'Not specified' && (
                        <span>{job.salary}</span>
                      )}
                      <span className="capitalize">{job.platform}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      job.status === 'active'
                        ? 'bg-blue-100 text-blue-700'
                        : job.status === 'completed'
                        ? 'bg-green-100 text-green-700'
                        : 'bg-gray-100 text-gray-700'
                    }`}>
                      {job.status}
                    </span>
                    {job.url && (
                      <a
                        href={job.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-2 text-gray-400 hover:text-primary-600"
                      >
                        <ExternalLink size={18} />
                      </a>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500">
              Showing {(page - 1) * 20 + 1} - {Math.min(page * 20, data.total)} of {data.total} jobs
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn btn-secondary"
              >
                Previous
              </button>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={!data.has_more}
                className="btn btn-secondary"
              >
                Next
              </button>
            </div>
          </div>
        </>
      ) : (
        <div className="card text-center py-12">
          <Briefcase className="mx-auto text-gray-400 mb-4" size={48} />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            No jobs found
          </h3>
          <p className="text-gray-500 mb-4">
            {query ? 'Try a different search term' : 'Add your first job to get started'}
          </p>
          <Link to="/jobs/add" className="btn btn-primary inline-flex items-center gap-2">
            <Plus size={20} />
            Add Job
          </Link>
        </div>
      )}
    </div>
  )
}
