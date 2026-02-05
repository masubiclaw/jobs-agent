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
}
