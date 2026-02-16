import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { jobsApi } from '../api'
import { Star, ExternalLink } from 'lucide-react'

export default function TopJobsPage() {
  const [minScore, setMinScore] = useState(0)

  const { data: jobs, isLoading } = useQuery({
    queryKey: ['topJobs', minScore],
    queryFn: () => jobsApi.getTop(50, minScore),
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

      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      ) : jobs && jobs.length > 0 ? (
        <div className="space-y-4">
          {jobs.map((job, index) => (
            <div
              key={job.id}
              className="card hover:shadow-md transition-shadow"
            >
              <div className="flex items-start gap-4">
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
                    <span>{job.location}</span>
                    {job.salary && job.salary !== 'Not specified' && (
                      <span>{job.salary}</span>
                    )}
                    <span className="capitalize">{job.platform}</span>
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
            {minScore > 0
              ? `No jobs match with ${minScore}%+ score. Try lowering the threshold.`
              : 'Run the job matcher to analyze jobs against your profile.'}
          </p>
        </div>
      )}
    </div>
  )
}
