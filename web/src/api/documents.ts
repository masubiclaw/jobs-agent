import apiClient from './client'
import { Document, DocumentRequest } from '../types'

export const documentsApi = {
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
