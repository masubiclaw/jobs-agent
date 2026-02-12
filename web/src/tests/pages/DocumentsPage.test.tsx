import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import DocumentsPage from '../../pages/DocumentsPage'

// Mock auth
vi.mock('../../contexts/AuthContext', async () => {
  const actual = await vi.importActual('../../contexts/AuthContext')
  return {
    ...actual,
    useAuth: () => ({
      user: { id: 'u1', email: 'test@test.com', name: 'Test', is_admin: false },
      isLoading: false,
    }),
  }
})

// Mock APIs - data must be inline in vi.mock factory (hoisting)
vi.mock('../../api/jobs', () => ({
  jobsApi: {
    getTop: vi.fn().mockResolvedValue([
      {
        id: 'job1', title: 'Software Engineer', company: 'Acme Corp', location: 'Remote',
        salary: '$150k', url: 'https://example.com/job1', description: 'A great job',
        platform: 'indeed', posted_date: '2026-01-01', cached_at: '2026-01-01',
        status: 'active', added_by: 'pipeline', notes: '',
        match: { keyword_score: 80, combined_score: 85, match_level: 'strong', toon_report: '' },
      },
      {
        id: 'job2', title: 'Backend Developer', company: 'Beta Inc', location: 'Seattle',
        salary: '$140k', url: 'https://example.com/job2', description: 'Another job',
        platform: 'linkedin', posted_date: '2026-01-02', cached_at: '2026-01-02',
        status: 'active', added_by: 'manual', notes: '',
      },
    ]),
    list: vi.fn().mockResolvedValue({
      jobs: [
        {
          id: 'job1', title: 'Software Engineer', company: 'Acme Corp', location: 'Remote',
          salary: '$150k', url: 'https://example.com/job1', description: 'A great job',
          platform: 'indeed', posted_date: '2026-01-01', cached_at: '2026-01-01',
          status: 'active', added_by: 'pipeline', notes: '',
          match: { keyword_score: 80, combined_score: 85, match_level: 'strong', toon_report: '' },
        },
        {
          id: 'job2', title: 'Backend Developer', company: 'Beta Inc', location: 'Seattle',
          salary: '$140k', url: 'https://example.com/job2', description: 'Another job',
          platform: 'linkedin', posted_date: '2026-01-02', cached_at: '2026-01-02',
          status: 'active', added_by: 'manual', notes: '',
        },
      ],
      total: 2, page: 1, page_size: 100, has_more: false,
    }),
  },
}))

vi.mock('../../api/documents', () => ({
  documentsApi: {
    list: vi.fn().mockResolvedValue([
      {
        id: 'doc1', job_id: 'job1', profile_id: 'p1', document_type: 'resume',
        job_title: 'Software Engineer', job_company: 'Acme Corp',
        job_url: 'https://example.com/job1', overall_score: 88,
        reviewed: false, is_good: null, pdf_path: '/path/to/resume.pdf',
        created_at: '2026-01-15T10:00:00',
      },
    ]),
    generateResume: vi.fn().mockResolvedValue({ id: 'doc2', content: 'resume content' }),
    generateCoverLetter: vi.fn().mockResolvedValue({ id: 'doc3', content: 'cover letter content' }),
    generatePackage: vi.fn().mockResolvedValue({ resume: { id: 'doc2' }, cover_letter: { id: 'doc3' } }),
    updateReview: vi.fn().mockResolvedValue(undefined),
    download: vi.fn().mockResolvedValue(new Blob(['pdf content'])),
  },
  DocumentListItem: {},
}))

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <DocumentsPage />
      </BrowserRouter>
    </QueryClientProvider>
  )
}

describe('DocumentsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders page title and generate section', () => {
    renderPage()
    expect(screen.getByText('Documents')).toBeInTheDocument()
    expect(screen.getByText('Generate Documents')).toBeInTheDocument()
  })

  it('renders job dropdown with placeholder', () => {
    renderPage()
    expect(screen.getByText('Select a job...')).toBeInTheDocument()
  })

  it('populates job dropdown with fetched jobs', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText(/Software Engineer - Acme Corp/)).toBeInTheDocument()
      expect(screen.getByText(/Backend Developer - Beta Inc/)).toBeInTheDocument()
    })
  })

  it('shows match score in dropdown for matched jobs', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText(/Software Engineer - Acme Corp \(85%\)/)).toBeInTheDocument()
    })
  })

  it('generate button is disabled when no job selected', () => {
    renderPage()
    const button = screen.getByRole('button', { name: /generate/i })
    expect(button).toBeDisabled()
  })

  it('generate button is enabled when job is selected', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText(/Software Engineer - Acme Corp/)).toBeInTheDocument()
    })

    const select = screen.getAllByRole('combobox')[0]
    fireEvent.change(select, { target: { value: 'job1' } })

    const button = screen.getByRole('button', { name: /generate/i })
    expect(button).not.toBeDisabled()
  })

  it('renders document type selector with all options', () => {
    renderPage()
    expect(screen.getByText('Both (Resume + Cover Letter)')).toBeInTheDocument()
    expect(screen.getByText('Resume Only')).toBeInTheDocument()
    expect(screen.getByText('Cover Letter Only')).toBeInTheDocument()
  })

  it('renders existing documents list', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Software Engineer')).toBeInTheDocument()
      expect(screen.getByText('Acme Corp')).toBeInTheDocument()
      expect(screen.getByText('Resume')).toBeInTheDocument()
    })
  })

  it('renders filter controls', () => {
    renderPage()
    expect(screen.getByText('All Types')).toBeInTheDocument()
    expect(screen.getByText('Resumes')).toBeInTheDocument()
    expect(screen.getByText('Cover Letters')).toBeInTheDocument()
    expect(screen.getByText('All Status')).toBeInTheDocument()
  })

  it('shows empty state when no documents', async () => {
    const { documentsApi } = await import('../../api/documents')
    vi.mocked(documentsApi.list).mockResolvedValueOnce([])

    renderPage()
    await waitFor(() => {
      expect(screen.getByText('No Documents Yet')).toBeInTheDocument()
    })
  })

  it('falls back to all jobs when top jobs is empty', async () => {
    const { jobsApi } = await import('../../api/jobs')
    vi.mocked(jobsApi.getTop).mockResolvedValueOnce([])

    renderPage()
    await waitFor(() => {
      expect(jobsApi.list).toHaveBeenCalledWith({ page_size: 100 })
    })
  })

  it('calls generatePackage when both type selected', async () => {
    const { documentsApi } = await import('../../api/documents')

    renderPage()
    await waitFor(() => {
      expect(screen.getByText(/Software Engineer - Acme Corp/)).toBeInTheDocument()
    })

    const select = screen.getAllByRole('combobox')[0]
    fireEvent.change(select, { target: { value: 'job1' } })

    const button = screen.getByRole('button', { name: /generate/i })
    fireEvent.click(button)

    await waitFor(() => {
      expect(documentsApi.generatePackage).toHaveBeenCalledWith({ job_id: 'job1' })
    })
  })

  it('calls generateResume when resume only selected', async () => {
    const { documentsApi } = await import('../../api/documents')

    renderPage()
    await waitFor(() => {
      expect(screen.getByText(/Software Engineer - Acme Corp/)).toBeInTheDocument()
    })

    const selects = screen.getAllByRole('combobox')
    fireEvent.change(selects[0], { target: { value: 'job1' } })
    fireEvent.change(selects[1], { target: { value: 'resume' } })

    const button = screen.getByRole('button', { name: /generate/i })
    fireEvent.click(button)

    await waitFor(() => {
      expect(documentsApi.generateResume).toHaveBeenCalledWith({ job_id: 'job1' })
    })
  })
})
