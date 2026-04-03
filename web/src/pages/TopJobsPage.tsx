import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { jobsApi } from '../api'
import { Star, ExternalLink, X, Filter, ThumbsDown } from 'lucide-react'

export default function TopJobsPage() {
  const [minScore, setMinScore] = useState(0)
  const [excludeFilter, setExcludeFilter] = useState('')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [dismissingId, setDismissingId] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const { data: jobs, isLoading, isError, error } = useQuery({
    queryKey: ['topJobs', minScore],
    queryFn: () => jobsApi.getTop(50, minScore),
  })

  const excludeMutation = useMutation({
    mutationFn: async (jobIds: string[]) => {
      await Promise.all(
        jobIds.map((id) => jobsApi.update(id, { status: 'archived' as any }))
      )
    },
    onSuccess: () => {
      setSelectedIds(new Set())
      queryClient.invalidateQueries({ queryKey: ['topJobs'] })
    },
  })

  const notInterestedMutation = useMutation({
    mutationFn: (jobId: string) => jobsApi.update(jobId, { status: 'archived' as any }),
    onMutate: async (jobId) => {
      setDismissingId(jobId)
      await queryClient.cancelQueries({ queryKey: ['topJobs', minScore] })
      const prev = queryClient.getQueryData(['topJobs', minScore])
      queryClient.setQueryData(['topJobs', minScore], (old: any) =>
        old?.filter((j: any) => j.id !== jobId)
      )
      return { prev }
    },
    onError: (_err, _id, context) => {
      queryClient.setQueryData(['topJobs', minScore], context?.prev)
    },
    onSettled: () => {
      setDismissingId(null)
      queryClient.invalidateQueries({ queryKey: ['topJobs'] })
    },
  })

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const selectAllFiltered = () => {
    if (!filteredJobs) return
    const allSelected = filteredJobs.every((j) => selectedIds.has(j.id))
    if (allSelected) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(filteredJobs.map((j) => j.id)))
    }
  }

  const excludeSelected = () => {
    if (selectedIds.size === 0) return
    excludeMutation.mutate(Array.from(selectedIds))
  }

  // Filter jobs by company/title/location text
  const filteredJobs = jobs?.filter((job) => {
    if (!excludeFilter) return true
    const q = excludeFilter.toLowerCase()
    return (
      job.title.toLowerCase().includes(q) ||
      job.company.toLowerCase().includes(q) ||
      (job.location && job.location.toLowerCase().includes(q))
    )
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Top Matches</h1>
          <p className="text-gray-600 mt-1">
            Jobs that best match your profile
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-500">Minimum Score:</label>
          <select
            value={minScore}
            onChange={(e) => setMinScore(parseInt(e.target.value))}
            className="input w-24"
          >
            <option value={0}>All</option>
            <option value={50}>50%+</option>
            <option value={60}>60%+</option>
            <option value={70}>70%+</option>
            <option value={80}>80%+</option>
          </select>
        </div>
      </div>

      {/* Filter & exclude bar */}
      <div className="card flex flex-wrap items-center gap-3">
        <Filter size={16} className="text-gray-400" />
        <input
          type="text"
          placeholder="Filter by company, title, or location..."
          value={excludeFilter}
          onChange={(e) => setExcludeFilter(e.target.value)}
          className="input flex-1 min-w-[200px]"
        />
        {filteredJobs && filteredJobs.length > 0 && (
          <button
            onClick={selectAllFiltered}
            className="btn btn-secondary text-sm"
          >
            {filteredJobs.every((j) => selectedIds.has(j.id))
              ? 'Deselect All'
              : `Select All (${filteredJobs.length})`}
          </button>
        )}
        {selectedIds.size > 0 && (
          <button
            onClick={excludeSelected}
            disabled={excludeMutation.isPending}
            className="btn btn-danger text-sm flex items-center gap-1"
          >
            <X size={14} />
            {excludeMutation.isPending
              ? 'Excluding...'
              : `Exclude ${selectedIds.size} job${selectedIds.size > 1 ? 's' : ''}`}
          </button>
        )}
      </div>

      {isError ? (
        <div className="card text-center py-8">
          <p className="text-red-600 font-medium">Failed to load matches</p>
          <p className="text-gray-500 text-sm mt-1">{(error as any)?.message || 'Network error'}</p>
        </div>
      ) : isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      ) : filteredJobs && filteredJobs.length > 0 ? (
        <div className="space-y-4">
          {filteredJobs.map((job, index) => (
            <div
              key={job.id}
              className={`card hover:shadow-md transition-shadow ${
                selectedIds.has(job.id) ? 'ring-2 ring-red-400' : ''
              }`}
            >
              <div className="flex items-start gap-4">
                <input
                  type="checkbox"
                  checked={selectedIds.has(job.id)}
                  onChange={() => toggleSelect(job.id)}
                  className="mt-3 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <div className={`flex-shrink-0 w-12 h-12 rounded-full flex items-center justify-center text-white font-bold ${
                  job.match?.combined_score && job.match.combined_score >= 80
                    ? 'bg-green-500'
                    : job.match?.combined_score && job.match.combined_score >= 60
                    ? 'bg-yellow-500'
                    : 'bg-gray-400'
                }`}>
                  #{index + 1}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <Link
                      to={`/jobs/${job.id}`}
                      className="text-lg font-semibold text-gray-900 hover:text-primary-600"
                    >
                      {job.title}
                    </Link>
                    {job.match && (
                      <span className={`px-3 py-1 rounded-full text-sm font-bold ${
                        job.match.combined_score >= 80
                          ? 'bg-green-100 text-green-700'
                          : job.match.combined_score >= 60
                          ? 'bg-yellow-100 text-yellow-700'
                          : 'bg-gray-100 text-gray-700'
                      }`}>
                        {job.match.combined_score}%
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
                    {job.cached_at && (
                      <span className="text-gray-400">{new Date(job.cached_at).toLocaleDateString()}</span>
                    )}
                  </div>
                  {job.match && (
                    <div className="flex flex-wrap items-center gap-4 mt-3 text-sm">
                      <span className="text-gray-500">
                        Skills: <span className="font-medium">{job.match.keyword_score}%</span>
                      </span>
                      {job.match.llm_score !== null && job.match.llm_score !== undefined && (
                        <span className="text-gray-500">
                          Overall Fit: <span className="font-medium">{job.match.llm_score}%</span>
                        </span>
                      )}
                      <span className="px-2 py-0.5 bg-gray-100 rounded text-gray-600 capitalize">
                        {job.match.match_level === 'strong' ? 'Strong Match'
                          : job.match.match_level === 'good' ? 'Good Match'
                          : 'Partial Match'}
                      </span>
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => notInterestedMutation.mutate(job.id)}
                    disabled={dismissingId === job.id}
                    className="p-2 text-gray-400 hover:text-red-600 transition-colors"
                    title="Not interested"
                  >
                    <ThumbsDown size={18} />
                  </button>
                  <Link
                    to={`/jobs/${job.id}`}
                    className="btn btn-secondary"
                  >
                    View Details
                  </Link>
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
      ) : (
        <div className="card text-center py-12">
          <Star className="mx-auto text-gray-400 mb-4" size={48} />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            No matches found
          </h3>
          <p className="text-gray-500">
            {excludeFilter
              ? 'No jobs match your filter.'
              : minScore > 0
              ? `No jobs match with ${minScore}%+ score. Try lowering the threshold.`
              : 'Run the job matcher to analyze jobs against your profile.'}
          </p>
        </div>
      )}
    </div>
  )
}
