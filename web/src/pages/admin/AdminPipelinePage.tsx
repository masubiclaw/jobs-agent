import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi, PipelineLogEntry } from '../../api/admin'
import {
  Play,
  Pause,
  RefreshCw,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  BarChart3,
  ScrollText,
  Timer,
} from 'lucide-react'

const STEPS = ['search', 'clean', 'fetch', 'match', 'generate']

export default function AdminPipelinePage() {
  const queryClient = useQueryClient()

  // Scheduler form state
  const [intervalHours, setIntervalHours] = useState(24)
  const [selectedSteps, setSelectedSteps] = useState<string[]>([...STEPS])
  const [messages, setMessages] = useState<{ type: 'success' | 'error'; text: string }[]>([])

  const logEndRef = useRef<HTMLDivElement>(null)

  const addMessage = (type: 'success' | 'error', text: string) => {
    setMessages((prev) => [...prev, { type, text }])
    setTimeout(() => setMessages((prev) => prev.slice(1)), 5000)
  }

  // Queries
  const statusQuery = useQuery({
    queryKey: ['pipeline-status'],
    queryFn: adminApi.getPipelineStatus,
    refetchInterval: 5000,
  })

  const statsQuery = useQuery({
    queryKey: ['pipeline-stats'],
    queryFn: adminApi.getPipelineStats,
    refetchInterval: 30000,
  })

  const historyQuery = useQuery({
    queryKey: ['pipeline-history'],
    queryFn: () => adminApi.getPipelineHistory(20),
    refetchInterval: 10000,
  })

  const logsQuery = useQuery({
    queryKey: ['pipeline-logs'],
    queryFn: () => adminApi.getPipelineLogs(200),
    refetchInterval: statusQuery.data?.is_running ? 3000 : 15000,
  })

  // Auto-scroll logs when running
  useEffect(() => {
    if (statusQuery.data?.is_running && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logsQuery.data, statusQuery.data?.is_running])

  // Sync interval from server
  useEffect(() => {
    if (statusQuery.data) {
      setIntervalHours(statusQuery.data.interval_hours)
    }
  }, [statusQuery.data?.interval_hours])

  // Mutations
  const runMutation = useMutation({
    mutationFn: () => adminApi.runPipeline(selectedSteps),
    onSuccess: (data) => {
      addMessage('success', data.message)
      queryClient.invalidateQueries({ queryKey: ['pipeline-status'] })
    },
    onError: () => addMessage('error', 'Failed to start pipeline'),
  })

  const schedulerMutation = useMutation({
    mutationFn: (enabled: boolean) => adminApi.updateScheduler(enabled, intervalHours),
    onSuccess: (data) => {
      addMessage('success', data.message)
      queryClient.invalidateQueries({ queryKey: ['pipeline-status'] })
    },
    onError: () => addMessage('error', 'Failed to update scheduler'),
  })

  const status = statusQuery.data
  const stats = statsQuery.data
  const runs = historyQuery.data?.runs || []
  const logs = logsQuery.data?.logs || []

  const toggleStep = (step: string) => {
    setSelectedSteps((prev) =>
      prev.includes(step) ? prev.filter((s) => s !== step) : [...prev, step]
    )
  }

  const getLogColor = (level: string) => {
    switch (level) {
      case 'ERROR': return 'text-red-400'
      case 'WARNING': return 'text-yellow-400'
      default: return 'text-gray-400'
    }
  }

  const formatDuration = (seconds: number | null) => {
    if (seconds === null) return '-'
    if (seconds < 60) return `${seconds.toFixed(1)}s`
    return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`
  }

  const formatTimeAgo = (iso: string | null) => {
    if (!iso) return 'Never'
    const diff = Date.now() - new Date(iso).getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return 'Just now'
    if (mins < 60) return `${mins}m ago`
    const hours = Math.floor(mins / 60)
    if (hours < 24) return `${hours}h ago`
    return `${Math.floor(hours / 24)}d ago`
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Pipeline Dashboard</h1>
        <p className="text-gray-600 mt-1">Manage the automated job pipeline</p>
      </div>

      {/* Status messages */}
      {messages.length > 0 && (
        <div className="space-y-2">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`p-3 rounded-lg flex items-center gap-2 ${
                msg.type === 'success'
                  ? 'bg-green-50 text-green-700 border border-green-200'
                  : 'bg-red-50 text-red-700 border border-red-200'
              }`}
            >
              {msg.type === 'success' ? <CheckCircle size={20} /> : <AlertCircle size={20} />}
              {msg.text}
            </div>
          ))}
        </div>
      )}

      {/* Top row: Scheduler + Manual Run */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Scheduler Control */}
        <div className="card">
          <div className="flex items-center gap-3 mb-4">
            <Clock className="text-blue-600" size={24} />
            <h2 className="text-lg font-semibold">Scheduler</h2>
            {status?.scheduler_enabled && (
              <span className="ml-auto px-2 py-1 text-xs font-medium bg-green-100 text-green-700 rounded-full">
                Active
              </span>
            )}
          </div>

          <div className="space-y-4">
            <div>
              <label className="label">Interval (hours)</label>
              <input
                type="number"
                value={intervalHours}
                onChange={(e) => setIntervalHours(parseFloat(e.target.value) || 24)}
                className="input w-32"
                min={0.5}
                step={0.5}
              />
            </div>

            {status?.next_run && status.scheduler_enabled && (
              <p className="text-sm text-gray-500">
                Next run: {new Date(status.next_run).toLocaleString()}
              </p>
            )}
            {status?.last_run && (
              <p className="text-sm text-gray-500">
                Last run: {formatTimeAgo(status.last_run)}
              </p>
            )}

            <div className="flex gap-2">
              {status?.scheduler_enabled ? (
                <button
                  onClick={() => schedulerMutation.mutate(false)}
                  disabled={schedulerMutation.isPending}
                  className="btn btn-danger"
                >
                  <Pause size={16} className="mr-1" />
                  Stop Scheduler
                </button>
              ) : (
                <button
                  onClick={() => schedulerMutation.mutate(true)}
                  disabled={schedulerMutation.isPending}
                  className="btn btn-primary"
                >
                  <Play size={16} className="mr-1" />
                  Start Scheduler
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Manual Run */}
        <div className="card">
          <div className="flex items-center gap-3 mb-4">
            <Play className="text-green-600" size={24} />
            <h2 className="text-lg font-semibold">Manual Run</h2>
            {status?.is_running && (
              <span className="ml-auto px-2 py-1 text-xs font-medium bg-yellow-100 text-yellow-700 rounded-full flex items-center gap-1">
                <RefreshCw size={12} className="animate-spin" />
                {status.current_step || 'Running'}
              </span>
            )}
          </div>

          <div className="space-y-4">
            <div>
              <label className="label mb-2">Steps</label>
              <div className="flex flex-wrap gap-2">
                {STEPS.map((step) => (
                  <label
                    key={step}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border cursor-pointer text-sm ${
                      selectedSteps.includes(step)
                        ? 'bg-primary-50 border-primary-300 text-primary-700'
                        : 'bg-gray-50 border-gray-200 text-gray-500'
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedSteps.includes(step)}
                      onChange={() => toggleStep(step)}
                      className="sr-only"
                    />
                    {step}
                  </label>
                ))}
              </div>
            </div>

            <button
              onClick={() => runMutation.mutate()}
              disabled={runMutation.isPending || status?.is_running || selectedSteps.length === 0}
              className="btn btn-primary"
            >
              {status?.is_running ? (
                <>
                  <RefreshCw size={16} className="mr-1 animate-spin" />
                  Running...
                </>
              ) : (
                <>
                  <Play size={16} className="mr-1" />
                  Run Pipeline Now
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
          {[
            { label: 'Total Runs', value: stats.total_runs, icon: BarChart3 },
            { label: 'Successful', value: stats.successful_runs, icon: CheckCircle },
            { label: 'Failed', value: stats.failed_runs, icon: XCircle },
            { label: 'Avg Duration', value: formatDuration(stats.avg_duration_seconds), icon: Timer },
            { label: 'Jobs Found', value: stats.total_jobs_found, icon: BarChart3 },
            { label: 'Matched', value: stats.total_jobs_matched, icon: BarChart3 },
            { label: 'Docs Generated', value: stats.total_docs_generated, icon: BarChart3 },
          ].map(({ label, value, icon: Icon }) => (
            <div key={label} className="card p-4">
              <div className="flex items-center gap-2 mb-1">
                <Icon size={14} className="text-gray-400" />
                <span className="text-xs text-gray-500">{label}</span>
              </div>
              <span className="text-xl font-bold text-gray-900">{value}</span>
            </div>
          ))}
        </div>
      )}

      {/* Run History */}
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <Clock className="text-purple-600" size={24} />
          <h2 className="text-lg font-semibold">Run History</h2>
        </div>

        {runs.length === 0 ? (
          <p className="text-gray-500 text-center py-8">No pipeline runs yet</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2 px-3 font-medium text-gray-500">Time</th>
                  <th className="text-left py-2 px-3 font-medium text-gray-500">Duration</th>
                  <th className="text-left py-2 px-3 font-medium text-gray-500">Status</th>
                  <th className="text-left py-2 px-3 font-medium text-gray-500">Steps</th>
                  <th className="text-right py-2 px-3 font-medium text-gray-500">Found</th>
                  <th className="text-right py-2 px-3 font-medium text-gray-500">Matched</th>
                  <th className="text-right py-2 px-3 font-medium text-gray-500">Docs</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-2 px-3 text-gray-600">
                      {formatTimeAgo(run.started_at)}
                    </td>
                    <td className="py-2 px-3 text-gray-600">
                      {formatDuration(run.duration_seconds)}
                    </td>
                    <td className="py-2 px-3">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                          run.status === 'success'
                            ? 'bg-green-100 text-green-700'
                            : run.status === 'failed'
                            ? 'bg-red-100 text-red-700'
                            : 'bg-yellow-100 text-yellow-700'
                        }`}
                      >
                        {run.status === 'running' && <RefreshCw size={10} className="animate-spin" />}
                        {run.status}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-gray-500 text-xs">
                      {run.steps.join(', ')}
                    </td>
                    <td className="py-2 px-3 text-right text-gray-600">{run.jobs_found}</td>
                    <td className="py-2 px-3 text-right text-gray-600">{run.jobs_matched}</td>
                    <td className="py-2 px-3 text-right text-gray-600">{run.docs_generated}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Log Viewer */}
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <ScrollText className="text-gray-600" size={24} />
          <h2 className="text-lg font-semibold">Pipeline Logs</h2>
          {status?.is_running && (
            <span className="text-xs text-gray-400">Auto-refreshing...</span>
          )}
        </div>

        <div className="bg-gray-900 rounded-lg p-4 max-h-80 overflow-y-auto font-mono text-xs">
          {logs.length === 0 ? (
            <p className="text-gray-500">No log entries yet</p>
          ) : (
            logs.map((log: PipelineLogEntry, i: number) => (
              <div key={i} className="py-0.5">
                <span className="text-gray-600">
                  {new Date(log.timestamp).toLocaleTimeString()}
                </span>{' '}
                <span className={getLogColor(log.level)}>[{log.level}]</span>{' '}
                <span className="text-gray-300">{log.message}</span>
              </div>
            ))
          )}
          <div ref={logEndRef} />
        </div>
      </div>
    </div>
  )
}
