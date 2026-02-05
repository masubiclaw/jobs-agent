// User types
export interface User {
  id: string
  email: string
  name: string
  is_admin: boolean
  created_at: string
}

export interface LoginCredentials {
  email: string
  password: string
}

export interface RegisterData extends LoginCredentials {
  name: string
}

export interface AuthToken {
  access_token: string
  token_type: string
  expires_in: number
}

// Profile types
export type SkillLevel = 'beginner' | 'intermediate' | 'advanced' | 'expert'
export type RemotePreference = 'remote' | 'hybrid' | 'onsite'

export interface Skill {
  name: string
  level: SkillLevel
  added_at?: string
}

export interface Experience {
  title: string
  company: string
  start_date: string
  end_date: string
  description: string
  added_at?: string
}

export interface Preferences {
  target_roles: string[]
  target_locations: string[]
  remote_preference: RemotePreference
  salary_min?: number
  salary_max?: number
  job_types: string[]
  industries: string[]
  excluded_companies: string[]
}

export interface Resume {
  summary: string
  content: string
  last_updated?: string
}

export interface Profile {
  id: string
  name: string
  email: string
  phone: string
  location: string
  created_at: string
  updated_at: string
  skills: Skill[]
  experience: Experience[]
  preferences: Preferences
  resume: Resume
  notes: string
  is_active: boolean
}

export interface ProfileListItem {
  id: string
  name: string
  location: string
  skills_count: number
  is_active: boolean
}

export interface ProfileCreate {
  name: string
  email?: string
  phone?: string
  location?: string
}

export interface ProfileUpdate {
  name?: string
  email?: string
  phone?: string
  location?: string
  notes?: string
  skills?: Skill[]
  experience?: Experience[]
  preferences?: Preferences
  resume?: Resume
}

// Job types
export type JobStatus = 'active' | 'completed' | 'archived'
export type JobAddMethod = 'manual' | 'url' | 'pdf' | 'scraped' | 'search'

export interface MatchResult {
  keyword_score: number
  llm_score?: number
  combined_score: number
  match_level: string
  toon_report: string
  cached_at?: string
}

export interface Job {
  id: string
  title: string
  company: string
  location: string
  salary: string
  url: string
  description: string
  platform: string
  posted_date: string
  cached_at: string
  status: JobStatus
  added_by: JobAddMethod
  notes: string
  match?: MatchResult
}

export interface JobListResponse {
  jobs: Job[]
  total: number
  page: number
  page_size: number
  has_more: boolean
}

export interface JobCreate {
  title?: string
  company?: string
  location?: string
  description?: string
  url?: string
  salary?: string
  plaintext?: string
  job_url?: string
}

export interface JobUpdate {
  status?: JobStatus
  notes?: string
}

// Document types
export type DocumentType = 'resume' | 'cover_letter' | 'package'

export interface QualityScores {
  fact_score: number
  keyword_score: number
  ats_score: number
  length_score: number
  overall_score: number
}

export interface Document {
  id: string
  job_id: string
  profile_id: string
  document_type: DocumentType
  content: string
  pdf_path?: string
  quality_scores: QualityScores
  iterations: number
  created_at: string
}

export interface DocumentRequest {
  job_id: string
  profile_id?: string
}

// Admin types
export interface SystemStats {
  jobs: {
    total: number
    by_platform: Record<string, number>
    top_companies: [string, number][]
  }
  matches: {
    total: number
    stats: Record<string, number>
  }
  vector_search: {
    available: boolean
    count: number
  }
  users: {
    total: number
  }
  cache: {
    dir: string
    created: string
    last_updated: string
    total_ever_added: number
  }
}
