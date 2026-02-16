import apiClient from './client'
import { Profile, ProfileListItem, ProfileCreate, ProfileUpdate } from '../types'

export const profilesApi = {
  list: async (): Promise<ProfileListItem[]> => {
    const response = await apiClient.get<ProfileListItem[]>('/profiles')
    return response.data
  },

  get: async (id: string): Promise<Profile> => {
    const response = await apiClient.get<Profile>(`/profiles/${id}`)
    return response.data
  },

  create: async (data: ProfileCreate): Promise<Profile> => {
    const response = await apiClient.post<Profile>('/profiles', data)
    return response.data
  },

  update: async (id: string, data: ProfileUpdate): Promise<Profile> => {
    const response = await apiClient.put<Profile>(`/profiles/${id}`, data)
    return response.data
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/profiles/${id}`)
  },

  activate: async (id: string): Promise<Profile> => {
    const response = await apiClient.post<Profile>(`/profiles/${id}/activate`)
    return response.data
  },

  importPdf: async (file: File): Promise<Profile> => {
    const formData = new FormData()
    formData.append('file', file)
    const response = await apiClient.post<Profile>('/profiles/import/pdf', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    })
    return response.data
  },

  importText: async (text: string): Promise<Profile> => {
    const response = await apiClient.post<Profile>('/profiles/import/text', { text }, {
      timeout: 300000,
    })
    return response.data
  },

  importLinkedIn: async (url: string): Promise<Profile> => {
    const response = await apiClient.post<Profile>('/profiles/import/linkedin', { url }, {
      timeout: 60000,
    })
    return response.data
  },
}
