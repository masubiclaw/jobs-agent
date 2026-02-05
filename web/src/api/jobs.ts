import apiClient from './client'
import { Job, JobListResponse, JobCreate, JobUpdate, JobStatus } from '../types'

interface ListJobsParams {
  page?: number
  page_size?: number
  status?: JobStatus
  company?: string
  location?: string
  query?: string
  semantic?: boolean
}

export const jobsApi = {
  list: async (params: ListJobsParams = {}): Promise<JobListResponse> => {
    const response = await apiClient.get<JobListResponse>('/jobs', { params })
    return response.data
  },

  getTop: async (limit: number = 10, minScore: number = 0): Promise<Job[]> => {
    const response = await apiClient.get<Job[]>('/jobs/top', {
      params: { limit, min_score: minScore },
    })
    return response.data
  },

  get: async (id: string): Promise<Job> => {
    const response = await apiClient.get<Job>(`/jobs/${id}`)
    return response.data
  },

  create: async (data: JobCreate): Promise<Job> => {
    const response = await apiClient.post<Job>('/jobs', data)
    return response.data
  },

  uploadPdf: async (file: File): Promise<Job> => {
    const formData = new FormData()
    formData.append('file', file)
    const response = await apiClient.post<Job>('/jobs/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },

  update: async (id: string, data: JobUpdate): Promise<Job> => {
    const response = await apiClient.put<Job>(`/jobs/${id}`, data)
    return response.data
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/jobs/${id}`)
  },
}
