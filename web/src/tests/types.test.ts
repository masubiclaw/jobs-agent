import { describe, it, expect } from 'vitest'
import type { 
  User, 
  Profile, 
  Job, 
  JobStatus, 
  SkillLevel,
  RemotePreference 
} from '../types'

describe('Types', () => {
  describe('User type', () => {
    it('has required properties', () => {
      const user: User = {
        id: '123',
        email: 'test@example.com',
        name: 'Test User',
        is_admin: false,
        created_at: '2024-01-01T00:00:00Z',
      }

      expect(user.id).toBe('123')
      expect(user.email).toBe('test@example.com')
      expect(user.name).toBe('Test User')
      expect(user.is_admin).toBe(false)
    })
  })

  describe('Job type', () => {
    it('has valid status values', () => {
      const statuses: JobStatus[] = ['active', 'completed', 'archived']
      
      expect(statuses).toContain('active')
      expect(statuses).toContain('completed')
      expect(statuses).toContain('archived')
    })

    it('allows creating job with all properties', () => {
      const job: Job = {
        id: 'job123',
        title: 'Software Engineer',
        company: 'Tech Corp',
        location: 'Seattle, WA',
        salary: '$150,000',
        url: 'https://example.com/job',
        description: 'Job description...',
        platform: 'linkedin',
        posted_date: '2024-01-01',
        cached_at: '2024-01-01T00:00:00Z',
        status: 'active',
        added_by: 'manual',
        notes: '',
      }

      expect(job.id).toBe('job123')
      expect(job.status).toBe('active')
    })
  })

  describe('Skill levels', () => {
    it('has valid skill levels', () => {
      const levels: SkillLevel[] = ['beginner', 'intermediate', 'advanced', 'expert']
      
      expect(levels).toHaveLength(4)
      expect(levels).toContain('beginner')
      expect(levels).toContain('expert')
    })
  })

  describe('Remote preferences', () => {
    it('has valid remote preferences', () => {
      const prefs: RemotePreference[] = ['remote', 'hybrid', 'onsite']
      
      expect(prefs).toHaveLength(3)
    })
  })
})
