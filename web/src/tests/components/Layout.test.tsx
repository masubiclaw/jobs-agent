import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import Layout from '../../components/Layout'
import { AuthProvider } from '../../contexts/AuthContext'

// Mock the auth context
vi.mock('../../contexts/AuthContext', async () => {
  const actual = await vi.importActual('../../contexts/AuthContext')
  return {
    ...actual,
    useAuth: () => ({
      user: { id: '1', name: 'Test User', email: 'test@example.com', is_admin: false },
      isLoading: false,
      logout: vi.fn(),
    }),
  }
})

describe('Layout', () => {
  it('renders navigation items', () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <Layout />
        </AuthProvider>
      </BrowserRouter>
    )

    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.getByText('Profiles')).toBeInTheDocument()
    expect(screen.getByText('Jobs')).toBeInTheDocument()
  })

  it('displays user name', () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <Layout />
        </AuthProvider>
      </BrowserRouter>
    )

    expect(screen.getByText('Test User')).toBeInTheDocument()
  })

  it('has sign out button', () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <Layout />
        </AuthProvider>
      </BrowserRouter>
    )

    expect(screen.getByText('Sign out')).toBeInTheDocument()
  })
})
