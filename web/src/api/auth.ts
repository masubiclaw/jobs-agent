import apiClient from './client'
import { User, LoginCredentials, RegisterData, AuthToken } from '../types'

export const authApi = {
  register: async (data: RegisterData): Promise<User> => {
    const response = await apiClient.post<User>('/auth/register', data)
    return response.data
  },

  login: async (credentials: LoginCredentials): Promise<AuthToken> => {
    const response = await apiClient.post<AuthToken>('/auth/login', credentials)
    return response.data
  },

  autoLogin: async (): Promise<AuthToken> => {
    const response = await apiClient.post<AuthToken>('/auth/auto-login')
    return response.data
  },

  getMe: async (): Promise<User> => {
    const response = await apiClient.get<User>('/auth/me')
    return response.data
  },
}
