import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { adminApi } from '../../api'
import { 
  Briefcase, 
  Users, 
  Database, 
  Search, 
  RefreshCw, 
  Trash2,
  ArrowRight 
} from 'lucide-react'

export default function AdminDashboard() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['adminStats'],
    queryFn: adminApi.getStats,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Admin Dashboard</h1>
        <p className="text-gray-600 mt-1">
          System overview and management tools
        </p>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="card">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
              <Briefcase className="text-blue-600" size={24} />
            </div>
            <div>
              <p className="text-sm text-gray-500">Total Jobs</p>
              <p className="text-2xl font-bold">{stats?.jobs.total || 0}</p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
              <Users className="text-green-600" size={24} />
            </div>
            <div>
              <p className="text-sm text-gray-500">Total Users</p>
              <p className="text-2xl font-bold">{stats?.users.total || 0}</p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
              <Database className="text-purple-600" size={24} />
            </div>
            <div>
              <p className="text-sm text-gray-500">Total Matches</p>
              <p className="text-2xl font-bold">{stats?.matches.total || 0}</p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-yellow-100 rounded-lg flex items-center justify-center">
              <Search className="text-yellow-600" size={24} />
            </div>
            <div>
              <p className="text-sm text-gray-500">Vector Count</p>
              <p className="text-2xl font-bold">{stats?.vector_search.count || 0}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Quick actions */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Link
            to="/admin/scraper"
            className="flex items-center gap-3 p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <RefreshCw size={20} className="text-blue-600" />
            <span>System Operations</span>
          </Link>
          <Link
            to="/admin/pipeline"
            className="flex items-center gap-3 p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <Search size={20} className="text-green-600" />
            <span>Pipeline Dashboard</span>
          </Link>
          <Link
            to="/admin/jobs"
            className="flex items-center gap-3 p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <RefreshCw size={20} className="text-purple-600" />
            <span>Manage Jobs</span>
          </Link>
          <Link
            to="/admin/scraper"
            className="flex items-center gap-3 p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <Trash2 size={20} className="text-red-600" />
            <span>Run Cleanup</span>
          </Link>
        </div>
      </div>

      {/* Jobs by platform */}
      {stats?.jobs.by_platform && Object.keys(stats.jobs.by_platform).length > 0 && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Jobs by Platform</h2>
            <Link
              to="/admin/jobs"
              className="text-sm text-primary-600 hover:text-primary-700 flex items-center gap-1"
            >
              View all <ArrowRight size={16} />
            </Link>
          </div>
          <div className="space-y-2">
            {Object.entries(stats.jobs.by_platform).map(([platform, count]) => (
              <div key={platform} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                <span className="capitalize">{platform}</span>
                <span className="font-medium">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top companies */}
      {stats?.jobs.top_companies && stats.jobs.top_companies.length > 0 && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Top Companies</h2>
          <div className="space-y-2">
            {stats.jobs.top_companies.slice(0, 10).map(([company, count], index) => (
              <div key={company} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                <div className="flex items-center gap-2">
                  <span className="text-gray-400 w-6">{index + 1}.</span>
                  <span>{company}</span>
                </div>
                <span className="font-medium">{count} jobs</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Cache info */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Cache Information</h2>
        <dl className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-gray-500">Cache Directory</dt>
            <dd className="font-mono text-xs">{stats?.cache.dir}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Total Ever Added</dt>
            <dd className="font-medium">{stats?.cache.total_ever_added || 0}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Created</dt>
            <dd className="font-medium">
              {stats?.cache.created ? new Date(stats.cache.created).toLocaleDateString() : 'Unknown'}
            </dd>
          </div>
          <div>
            <dt className="text-gray-500">Last Updated</dt>
            <dd className="font-medium">
              {stats?.cache.last_updated ? new Date(stats.cache.last_updated).toLocaleString() : 'Unknown'}
            </dd>
          </div>
        </dl>
      </div>
    </div>
  )
}
