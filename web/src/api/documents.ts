import apiClient from './client'
import { Document, DocumentRequest } from '../types'

export interface DocumentListItem {
  id: string
  job_id: string
  profile_id: string
  document_type: 'resume' | 'cover_letter'
  job_title: string
  job_company: string
  job_url: string | null
  overall_score: number
  reviewed: boolean
  is_good: boolean | null
  pdf_path: string | null
  created_at: string
}

export const documentsApi = {
  list: async (limit: number = 100): Promise<DocumentListItem[]> => {
    const response = await apiClient.get<DocumentListItem[]>('/documents', { params: { limit } })
    return response.data
  },

  updateReview: async (docId: string, reviewed?: boolean, is_good?: boolean | null): Promise<void> => {
    await apiClient.patch(`/documents/${docId}/review`, { reviewed, is_good })
  },

  generateResume: async (request: DocumentRequest): Promise<Document> => {
    const response = await apiClient.post<Document>('/documents/resume', request)
    return response.data
  },

  generateCoverLetter: async (request: DocumentRequest): Promise<Document> => {
    const response = await apiClient.post<Document>('/documents/cover-letter', request)
    return response.data
  },

  generatePackage: async (request: DocumentRequest): Promise<{ resume: Document | null; cover_letter: Document | null }> => {
    const response = await apiClient.post('/documents/package', request)
    return response.data
  },

  download: async (documentId: string): Promise<Blob> => {
    const response = await apiClient.get(`/documents/${documentId}/download`, {
      responseType: 'blob',
    })
    return response.data
  },
}
