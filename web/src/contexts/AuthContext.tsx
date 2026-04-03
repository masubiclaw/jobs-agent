import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { User, LoginCredentials, RegisterData } from '../types'
import { authApi } from '../api'

interface AuthContextType {
  user: User | null
  isLoading: boolean
  login: (credentials: LoginCredentials) => Promise<void>
  register: (data: RegisterData) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    // Check for existing token and load user
    const token = localStorage.getItem('auth_token')
    if (token) {
      loadUser()
    } else {
      // No token — auto-login as default admin to bypass login screen
      autoLogin()
    }
  }, [])

  const autoLogin = async () => {
    try {
      const { access_token } = await authApi.autoLogin()
      localStorage.setItem('auth_token', access_token)
      await loadUser()
    } catch {
      // Auto-login failed — fall back to normal login flow
      setIsLoading(false)
    }
  }

  const loadUser = async () => {
    try {
      const userData = await authApi.getMe()
      setUser(userData)
    } catch (error: any) {
      // Clear token on auth errors (401) or if user data can't be loaded
      if (error?.response?.status === 401 || error?.response?.status === 403) {
        localStorage.removeItem('auth_token')
      } else {
        // Network error — retry once after a short delay
        try {
          await new Promise(r => setTimeout(r, 2000))
          const userData = await authApi.getMe()
          setUser(userData)
          return
        } catch {
          localStorage.removeItem('auth_token')
        }
      }
    } finally {
      setIsLoading(false)
    }
  }

  const login = async (credentials: LoginCredentials) => {
    const { access_token } = await authApi.login(credentials)
    localStorage.setItem('auth_token', access_token)
    await loadUser()
  }

  const register = async (data: RegisterData) => {
    await authApi.register(data)
    // Auto-login after registration
    await login({ email: data.email, password: data.password })
  }

  const logout = () => {
    localStorage.removeItem('auth_token')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
