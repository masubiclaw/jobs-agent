import apiClient from './client'
import { SystemStats, User, JobListResponse } from '../types'

export const adminApi = {
  getStats: async (): Promise<SystemStats> => {
    const response = await apiClient.get<SystemStats>('/admin/stats')
    return response.data
  },

  listJobs: async (page: number = 1, pageSize: number = 50): Promise<JobListResponse> => {
    const response = await apiClient.get<JobListResponse>('/admin/jobs', {
      params: { page, page_size: pageSize },
    })
    return response.data
  },

  deleteJob: async (jobId: string): Promise<void> => {
    await apiClient.delete(`/admin/jobs/${jobId}`)
  },

  listUsers: async (): Promise<{ users: User[]; total: number }> => {
    const response = await apiClient.get('/admin/users')
    return response.data
  },

  runScraper: async (params: {
    file_path?: string
    categories?: string
    max_sources?: number
  }): Promise<{ status: string; message: string }> => {
    const response = await apiClient.post('/admin/scraper/run', null, { params })
    return response.data
  },

  runSearcher: async (params: {
    search_term: string
    location?: string
    sites?: string
    results_wanted?: number
  }): Promise<{ status: string; message: string }> => {
    const response = await apiClient.post('/admin/searcher/run', null, { params })
    return response.data
  },

  runMatcher: async (params: {
    profile_id?: string
    llm_pass?: boolean
    limit?: number
  }): Promise<{ status: string; message: string }> => {
    const response = await apiClient.post('/admin/matcher/run', null, { params })
    return response.data
  },

  runCleanup: async (params: {
    days_old?: number
    check_urls?: boolean
  }): Promise<{ status: string; message: string }> => {
    const response = await apiClient.post('/admin/cleanup', null, { params })
    return response.data
  },

  // Pipeline endpoints
  getPipelineStatus: async (): Promise<PipelineStatus> => {
    const response = await apiClient.get('/admin/pipeline/status')
    return response.data
  },

  runPipeline: async (steps?: string[]): Promise<{ status: string; message: string }> => {
    const response = await apiClient.post('/admin/pipeline/run', { steps })
    return response.data
  },

  updateScheduler: async (enabled: boolean, interval_hours: number, start_time?: string): Promise<{ status: string; message: string }> => {
    const response = await apiClient.post('/admin/pipeline/scheduler', { enabled, interval_hours, start_time })
    return response.data
  },

  getPipelineHistory: async (limit: number = 20): Promise<{ runs: PipelineRunHistory[] }> => {
    const response = await apiClient.get('/admin/pipeline/history', { params: { limit } })
    return response.data
  },

  getPipelineLogs: async (limit: number = 200): Promise<{ logs: PipelineLogEntry[] }> => {
    const response = await apiClient.get('/admin/pipeline/logs', { params: { limit } })
    return response.data
  },

  getPipelineStats: async (): Promise<PipelineStats> => {
    const response = await apiClient.get('/admin/pipeline/stats')
    return response.data
  },
}

// Pipeline types
export interface PipelineStatus {
  scheduler_enabled: boolean
  interval_hours: number
  is_running: boolean
  last_run: string | null
  next_run: string | null
  current_step: string | null
}

export interface PipelineRunHistory {
  id: string
  started_at: string
  finished_at: string | null
  duration_seconds: number | null
  status: 'running' | 'success' | 'failed'
  steps: string[]
  jobs_found: number
  jobs_matched: number
  docs_generated: number
  error: string | null
}

export interface PipelineLogEntry {
  timestamp: string
  level: string
  message: string
}

export interface PipelineStats {
  total_runs: number
  successful_runs: number
  failed_runs: number
  avg_duration_seconds: number
  total_jobs_found: number
  total_jobs_matched: number
  total_docs_generated: number
}
