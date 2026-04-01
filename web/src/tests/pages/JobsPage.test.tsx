import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import JobsPage from '../../pages/JobsPage'

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

vi.mock('../../api/jobs', () => ({
  jobsApi: {
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
          status: 'applied', added_by: 'manual', notes: 'Applied last week',
        },
      ],
      total: 2, page: 1, page_size: 20, has_more: false,
    }),
  },
}))

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <JobsPage />
      </BrowserRouter>
    </QueryClientProvider>
  )
}

describe('JobsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders page title', () => {
    renderPage()
    expect(screen.getByText('Jobs')).toBeInTheDocument()
  })

  it('renders search input with live search placeholder', () => {
    renderPage()
    expect(screen.getByPlaceholderText('Search jobs... (live)')).toBeInTheDocument()
  })

  it('renders sort buttons', () => {
    renderPage()
    expect(screen.getByText('Title')).toBeInTheDocument()
    expect(screen.getByText('Company')).toBeInTheDocument()
    expect(screen.getByText('Match Score')).toBeInTheDocument()
    expect(screen.getByText('Date Added')).toBeInTheDocument()
  })

  it('renders all application status filter options', () => {
    renderPage()
    const select = screen.getAllByRole('combobox')[0]
    expect(select).toBeInTheDocument()
    // Check all status options exist in the status dropdown
    expect(screen.getByText('Applied')).toBeInTheDocument()
    expect(screen.getByText('Interviewing')).toBeInTheDocument()
    expect(screen.getByText('Offered')).toBeInTheDocument()
    expect(screen.getByText('Rejected')).toBeInTheDocument()
  })

  it('renders jobs with match scores', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Software Engineer')).toBeInTheDocument()
      expect(screen.getByText('85% match')).toBeInTheDocument()
    })
  })

  it('shows applied status badge', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('applied')).toBeInTheDocument()
    })
  })

  it('shows job notes inline', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Applied last week')).toBeInTheDocument()
    })
  })

  it('has page size selector after loading', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('per page')).toBeInTheDocument()
    })
  })

  it('has Add Job button', () => {
    renderPage()
    expect(screen.getByText('Add Job')).toBeInTheDocument()
  })
})
