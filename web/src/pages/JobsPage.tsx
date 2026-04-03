import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { jobsApi } from '../api'
import { JobStatus } from '../types'
import { Briefcase, Search, Filter, Plus, ExternalLink, ArrowUpDown, ChevronUp, ChevronDown, ThumbsDown } from 'lucide-react'

type SortField = 'title' | 'company' | 'score' | 'date'
type SortDir = 'asc' | 'desc'

export default function JobsPage() {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<JobStatus | ''>('active')
  const queryClient = useQueryClient()
  const [searchInput, setSearchInput] = useState('')
  const [sortField, setSortField] = useState<SortField>('date')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [dismissingId, setDismissingId] = useState<string | null>(null)

  // Debounced live search
  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(searchInput)
      setPage(1)
    }, 300)
    return () => clearTimeout(timer)
  }, [searchInput])

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['jobs', { page, pageSize, query, status, sortField }],
    queryFn: () =>
      jobsApi.list({
        page,
        page_size: pageSize,
        query: query || undefined,
        status: status || undefined,
        sort_by: sortField,
      }),
  })

  const notInterestedMutation = useMutation({
    mutationFn: (jobId: string) => jobsApi.update(jobId, { status: 'archived' as any }),
    onMutate: async (jobId) => {
      setDismissingId(jobId)
      const qk = ['jobs', { page, pageSize, query, status }]
      await queryClient.cancelQueries({ queryKey: qk })
      const prev = queryClient.getQueryData(qk)
      queryClient.setQueryData(qk, (old: any) =>
        old ? { ...old, jobs: old.jobs.filter((j: any) => j.id !== jobId), total: old.total - 1 } : old
      )
      return { prev, qk }
    },
    onError: (_err, _id, context) => {
      if (context?.qk) queryClient.setQueryData(context.qk, context.prev)
    },
    onSettled: () => {
      setDismissingId(null)
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  // Server-side sorting — data comes pre-sorted
  const sortedJobs = data?.jobs ?? []

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDir(field === 'score' ? 'desc' : 'asc')
    }
  }

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <ArrowUpDown size={14} className="text-gray-300" />
    return sortDir === 'asc'
      ? <ChevronUp size={14} className="text-primary-600" />
      : <ChevronDown size={14} className="text-primary-600" />
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
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={20} />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search jobs... (live)"
              className="input pl-10"
            />
          </div>

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
              <option value="applied">Applied</option>
              <option value="interviewing">Interviewing</option>
              <option value="offered">Offered</option>
              <option value="rejected">Rejected</option>
              <option value="completed">Completed</option>
              <option value="archived">Archived</option>
            </select>
          </div>
        </div>

        {/* Sort buttons */}
        <div className="flex items-center gap-3 mt-3 pt-3 border-t border-gray-100">
          <span className="text-xs text-gray-500 uppercase tracking-wide">Sort by</span>
          {([
            ['title', 'Title'],
            ['company', 'Company'],
            ['score', 'Match Score'],
            ['date', 'Date Added'],
          ] as [SortField, string][]).map(([field, label]) => (
            <button
              key={field}
              onClick={() => toggleSort(field)}
              className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                sortField === field
                  ? 'bg-primary-50 text-primary-700'
                  : 'text-gray-500 hover:bg-gray-100'
              }`}
            >
              {label}
              <SortIcon field={field} />
            </button>
          ))}
        </div>
      </div>

      {/* Job list */}
      {isError ? (
        <div className="card text-center py-8">
          <p className="text-red-600 font-medium">Failed to load jobs</p>
          <p className="text-gray-500 text-sm mt-1">{(error as any)?.message || 'Network error'}</p>
        </div>
      ) : isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      ) : data && sortedJobs.length > 0 ? (
        <>
          <div className="space-y-4">
            {sortedJobs.map((job) => (
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
                      {job.location && job.location.toLowerCase() !== 'unknown' && (
                        <span>{job.location}</span>
                      )}
                      {job.salary && job.salary !== 'Not specified' && (
                        <span>{job.salary}</span>
                      )}
                      {job.platform && job.platform.toLowerCase() !== 'unknown' && (
                        <span className="capitalize">{job.platform}</span>
                      )}
                      {job.notes && (
                        <span className="text-primary-600 italic truncate max-w-[200px]">{job.notes}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      job.status === 'active'
                        ? 'bg-blue-100 text-blue-700'
                        : job.status === 'applied'
                        ? 'bg-indigo-100 text-indigo-700'
                        : job.status === 'interviewing'
                        ? 'bg-amber-100 text-amber-700'
                        : job.status === 'offered'
                        ? 'bg-emerald-100 text-emerald-700'
                        : job.status === 'rejected'
                        ? 'bg-red-100 text-red-700'
                        : job.status === 'completed'
                        ? 'bg-green-100 text-green-700'
                        : 'bg-gray-100 text-gray-700'
                    }`}>
                      {job.status}
                    </span>
                    <button
                      onClick={(e) => {
                        e.preventDefault()
                        notInterestedMutation.mutate(job.id)
                      }}
                      disabled={dismissingId === job.id}
                      className="p-2 text-gray-400 hover:text-red-600 transition-colors"
                      title="Not interested"
                    >
                      <ThumbsDown size={18} />
                    </button>
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
            <div className="flex items-center gap-4">
              <p className="text-sm text-gray-500">
                Showing {(page - 1) * pageSize + 1} - {Math.min(page * pageSize, data.total)} of {data.total} jobs
              </p>
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value))
                  setPage(1)
                }}
                className="input py-1 text-sm w-20"
              >
                <option value={20}>20</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
              <span className="text-sm text-gray-400">per page</span>
            </div>
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
            {query ? `No results for "${query}". Try a different search term.` : 'Add your first job to get started.'}
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
