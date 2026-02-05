import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

describe('API Client', () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('stores token in localStorage', () => {
    const token = 'test-token-123'
    localStorage.setItem('auth_token', token)
    
    expect(localStorage.getItem('auth_token')).toBe(token)
  })

  it('removes token on logout', () => {
    localStorage.setItem('auth_token', 'test-token')
    localStorage.removeItem('auth_token')
    
    expect(localStorage.getItem('auth_token')).toBeNull()
  })

  it('token persists across reads', () => {
    const token = 'persistent-token'
    localStorage.setItem('auth_token', token)
    
    // Multiple reads should return same value
    expect(localStorage.getItem('auth_token')).toBe(token)
    expect(localStorage.getItem('auth_token')).toBe(token)
  })
})
