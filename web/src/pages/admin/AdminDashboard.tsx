import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { adminApi, LLMQueueStats } from '../../api'
import {
  Briefcase,
  Users,
  Database,
  Search,
  RefreshCw,
  Trash2,
  ArrowRight,
  Cpu
} from 'lucide-react'

export default function AdminDashboard() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['adminStats'],
    queryFn: adminApi.getStats,
  })

  const { data: llmStats } = useQuery({
    queryKey: ['llmQueueStats'],
    queryFn: adminApi.getLLMQueueStats,
    refetchInterval: 5000,
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

      {/* Jobs by platform and top companies removed per user request */}

      {/* LLM Queue */}
      <div className="card">
        <div className="flex items-center gap-2 mb-4">
          <Cpu size={20} className="text-purple-600" />
          <h2 className="text-lg font-semibold">LLM Queue</h2>
          {llmStats?.in_flight ? (
            <span className="ml-2 px-2 py-0.5 bg-green-100 text-green-700 rounded-full text-xs font-medium animate-pulse">Processing</span>
          ) : null}
          {!llmStats && (
            <span className="ml-2 text-sm text-gray-400">Loading...</span>
          )}
        </div>

        {/* Queue summary */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
          <div>
            <p className="text-sm text-gray-500">Queue Depth</p>
            <p className={`text-2xl font-bold ${(llmStats?.queue_depth ?? 0) > 5 ? 'text-red-600' : (llmStats?.queue_depth ?? 0) > 0 ? 'text-yellow-600' : 'text-green-600'}`}>
              {llmStats?.queue_depth ?? 0}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-500">In Flight</p>
            <p className="text-2xl font-bold">{llmStats?.in_flight ?? 0}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Total Requests</p>
            <p className="text-2xl font-bold">{llmStats?.total_requests ?? 0}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Avg Duration</p>
            <p className="text-2xl font-bold">{llmStats?.avg_duration_seconds ?? 0}s</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Avg Wait</p>
            <p className="text-2xl font-bold">{llmStats?.avg_queue_wait_seconds ?? 0}s</p>
          </div>
        </div>

        {/* By type breakdown */}
        {llmStats?.by_type && Object.keys(llmStats.by_type).length > 0 && (
          <div className="mb-6">
            <h3 className="text-sm font-medium text-gray-500 mb-2">By Request Type</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-2 pr-4 font-medium text-gray-500">Type</th>
                    <th className="text-right py-2 px-4 font-medium text-gray-500">Count</th>
                    <th className="text-right py-2 px-4 font-medium text-gray-500">Avg Duration</th>
                    <th className="text-right py-2 px-4 font-medium text-gray-500">Avg Wait</th>
                    <th className="text-right py-2 pl-4 font-medium text-gray-500">Success Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(llmStats.by_type).map(([type, data]) => (
                    <tr key={type} className="border-b border-gray-100">
                      <td className="py-2 pr-4 font-medium capitalize">{type.replace('_', ' ')}</td>
                      <td className="py-2 px-4 text-right">{data.count}</td>
                      <td className="py-2 px-4 text-right">{data.avg_duration}s</td>
                      <td className="py-2 px-4 text-right">{data.avg_wait}s</td>
                      <td className="py-2 pl-4 text-right">
                        <span className={data.success_rate >= 0.95 ? 'text-green-600' : data.success_rate >= 0.8 ? 'text-yellow-600' : 'text-red-600'}>
                          {(data.success_rate * 100).toFixed(0)}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Current request */}
        {(llmStats as any)?.current && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg">
            <h3 className="text-sm font-medium text-green-700 mb-1">Currently Processing</h3>
            <div className="flex items-center gap-4 text-sm">
              <span className="capitalize font-medium">{(llmStats as any).current.type.replace('_', ' ')}</span>
              <span className="text-gray-600">{(llmStats as any).current.model}</span>
              <span className="text-green-600 font-mono">{(llmStats as any).current.running_seconds}s running</span>
              <span className="text-gray-400">waited {(llmStats as any).current.waited_seconds}s</span>
            </div>
          </div>
        )}

        {/* Pending queue */}
        {(llmStats as any)?.pending?.length > 0 && (
          <div className="mb-4">
            <h3 className="text-sm font-medium text-gray-500 mb-2">Queued Requests ({(llmStats as any).pending.length})</h3>
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {(llmStats as any).pending.map((entry: any, i: number) => (
                <div key={i} className="flex items-center gap-3 text-xs py-1.5 px-2 bg-yellow-50 border border-yellow-100 rounded">
                  <span className="w-2 h-2 rounded-full bg-yellow-400" />
                  <span className="capitalize font-medium w-24">{entry.type.replace('_', ' ')}</span>
                  <span className="text-gray-500">{entry.model}</span>
                  <span className="text-yellow-600">waiting {entry.waiting_seconds}s</span>
                  <span className="text-gray-400 text-xs truncate max-w-[200px]">{entry.prompt_preview}</span>
                  <span className="ml-auto text-gray-400">{entry.priority_name}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recent requests */}
        {llmStats?.recent && llmStats.recent.length > 0 && (
          <div>
            <h3 className="text-sm font-medium text-gray-500 mb-2">Recent Requests</h3>
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {llmStats.recent.map((entry, i) => (
                <div key={i} className="flex items-center gap-3 text-xs py-1 border-b border-gray-50">
                  <span className={`w-2 h-2 rounded-full ${entry.success ? 'bg-green-400' : 'bg-red-400'}`} />
                  <span className="capitalize font-medium w-24">{entry.type.replace('_', ' ')}</span>
                  <span className="text-gray-500">{entry.duration}s</span>
                  <span className="text-gray-400">wait {entry.wait}s</span>
                  <span className="text-gray-400 ml-auto">{new Date(entry.finished_at).toLocaleTimeString()}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {(llmStats?.total_requests === 0) && (
          <p className="text-sm text-gray-400">No LLM requests yet. Queue will populate as matching, document generation, or job extraction runs.</p>
        )}

        {(llmStats?.total_failures ?? 0) > 0 && (
          <div className="mt-3 text-sm text-red-600">
            {llmStats!.total_failures} failed request{llmStats!.total_failures > 1 ? 's' : ''} of {llmStats!.total_requests} total
          </div>
        )}
      </div>

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
