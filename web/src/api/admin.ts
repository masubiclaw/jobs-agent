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
}
