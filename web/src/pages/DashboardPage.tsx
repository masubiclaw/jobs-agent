import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { profilesApi, jobsApi } from '../api'
import { Briefcase, User, Star, Plus, ArrowRight, CheckCircle, Circle } from 'lucide-react'

export default function DashboardPage() {
  const { user } = useAuth()

  const { data: profiles } = useQuery({
    queryKey: ['profiles'],
    queryFn: profilesApi.list,
  })

  const { data: jobs } = useQuery({
    queryKey: ['jobs', { page: 1, page_size: 5 }],
    queryFn: () => jobsApi.list({ page: 1, page_size: 5 }),
  })

  const { data: topJobs } = useQuery({
    queryKey: ['topJobs', 5],
    queryFn: () => jobsApi.getTop(5, 50),
  })

  const activeProfile = profiles?.find(p => p.is_active)
  const hasProfile = profiles && profiles.length > 0
  const hasJobs = jobs && jobs.total > 0
  const hasMatches = topJobs && topJobs.length > 0
  const isNewUser = !hasProfile

  return (
    <div className="space-y-8">
      {/* Welcome header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          {isNewUser ? `Welcome, ${user?.name}!` : `Welcome back, ${user?.name}!`}
        </h1>
        <p className="text-gray-600 mt-1">
          {isNewUser
            ? 'Let\'s get you set up to find your next role.'
            : 'Here\'s an overview of your job search progress.'}
        </p>
      </div>

      {/* Getting Started checklist for new users */}
      {isNewUser && (
        <div className="card border-2 border-primary-200 bg-primary-50/30">
          <h2 className="text-lg font-semibold mb-4">Getting Started</h2>
          <div className="space-y-3">
            <Link to="/profiles/new" className="flex items-center gap-3 p-3 bg-white rounded-lg border border-gray-200 hover:border-primary-300 transition-colors">
              {hasProfile
                ? <CheckCircle size={20} className="text-green-500" />
                : <Circle size={20} className="text-gray-300" />}
              <div>
                <p className="font-medium">Create your profile</p>
                <p className="text-sm text-gray-500">Add your skills, experience, and job preferences</p>
              </div>
              <ArrowRight size={16} className="ml-auto text-gray-400" />
            </Link>
            <Link to="/jobs" className="flex items-center gap-3 p-3 bg-white rounded-lg border border-gray-200 hover:border-primary-300 transition-colors">
              {hasJobs
                ? <CheckCircle size={20} className="text-green-500" />
                : <Circle size={20} className="text-gray-300" />}
              <div>
                <p className="font-medium">Browse or add jobs</p>
                <p className="text-sm text-gray-500">Find open positions or paste a job URL</p>
              </div>
              <ArrowRight size={16} className="ml-auto text-gray-400" />
            </Link>
            <Link to="/jobs/top" className="flex items-center gap-3 p-3 bg-white rounded-lg border border-gray-200 hover:border-primary-300 transition-colors">
              {hasMatches
                ? <CheckCircle size={20} className="text-green-500" />
                : <Circle size={20} className="text-gray-300" />}
              <div>
                <p className="font-medium">View your matches</p>
                <p className="text-sm text-gray-500">See which jobs fit your profile best</p>
              </div>
              <ArrowRight size={16} className="ml-auto text-gray-400" />
            </Link>
          </div>
        </div>
      )}

      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="card">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-primary-100 rounded-lg flex items-center justify-center">
              <User className="text-primary-600" size={24} />
            </div>
            <div>
              <p className="text-sm text-gray-500">Active Profile</p>
              <p className="text-lg font-semibold">
                {activeProfile?.name || 'None'}
              </p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
              <Briefcase className="text-green-600" size={24} />
            </div>
            <div>
              <p className="text-sm text-gray-500">Total Jobs</p>
              <p className="text-lg font-semibold">{jobs?.total || 0}</p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-yellow-100 rounded-lg flex items-center justify-center">
              <Star className="text-yellow-600" size={24} />
            </div>
            <div>
              <p className="text-sm text-gray-500">Top Matches</p>
              <p className="text-lg font-semibold">{topJobs?.length || 0}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Quick actions */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Link
            to="/profiles/new"
            className="flex items-center gap-3 p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <Plus size={20} className="text-primary-600" />
            <span>Create Profile</span>
          </Link>
          <Link
            to="/jobs/add"
            className="flex items-center gap-3 p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <Plus size={20} className="text-green-600" />
            <span>Add Job</span>
          </Link>
          <Link
            to="/jobs/top"
            className="flex items-center gap-3 p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <Star size={20} className="text-yellow-600" />
            <span>View Top Matches</span>
          </Link>
          <Link
            to="/jobs"
            className="flex items-center gap-3 p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <Briefcase size={20} className="text-blue-600" />
            <span>Browse Jobs</span>
          </Link>
        </div>
      </div>

      {/* Top matches preview */}
      {topJobs && topJobs.length > 0 && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Top Matches</h2>
            <Link
              to="/jobs/top"
              className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1"
            >
              View all <ArrowRight size={16} />
            </Link>
          </div>
          <div className="space-y-3">
            {topJobs.slice(0, 5).map((job) => (
              <Link
                key={job.id}
                to={`/jobs/${job.id}`}
                className="flex items-center justify-between p-3 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <div className="min-w-0 flex-1">
                  <p className="font-medium truncate">{job.title}</p>
                  <p className="text-sm text-gray-500 truncate">
                    {job.company} - {job.location}
                  </p>
                </div>
                {job.match && (
                  <div className={`ml-3 flex-shrink-0 px-3 py-1 rounded-full text-sm font-medium ${
                    job.match.combined_score >= 80
                      ? 'bg-green-100 text-green-700'
                      : job.match.combined_score >= 60
                      ? 'bg-yellow-100 text-yellow-700'
                      : 'bg-gray-100 text-gray-700'
                  }`}>
                    {job.match.combined_score}%
                  </div>
                )}
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
