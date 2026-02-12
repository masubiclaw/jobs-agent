import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ProfileFormPage from '../../pages/ProfileFormPage'

// Mock profilesApi
const mockCreate = vi.fn()
const mockUpdate = vi.fn()
const mockGet = vi.fn()

vi.mock('../../api', () => ({
  profilesApi: {
    create: (...args: any[]) => mockCreate(...args),
    update: (...args: any[]) => mockUpdate(...args),
    get: (...args: any[]) => mockGet(...args),
    list: vi.fn().mockResolvedValue([]),
    delete: vi.fn(),
    activate: vi.fn(),
    importPdf: vi.fn(),
    importLinkedIn: vi.fn(),
  },
}))

// Mock navigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
}

function renderCreateMode() {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={['/profiles/new']}>
        <Routes>
          <Route path="/profiles/new" element={<ProfileFormPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

function renderEditMode(profileData: any) {
  mockGet.mockResolvedValue(profileData)
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={[`/profiles/${profileData.id}`]}>
        <Routes>
          <Route path="/profiles/:id" element={<ProfileFormPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

const mockProfile = {
  id: 'test_user',
  name: 'Test User',
  email: 'test@test.com',
  phone: '5551234567',
  location: 'Seattle, WA',
  created_at: '2026-02-10T00:00:00',
  updated_at: '2026-02-10T00:00:00',
  skills: [
    { name: 'Python', level: 'advanced', added_at: '2026-02-10T00:00:00' },
    { name: 'React', level: 'intermediate', added_at: '2026-02-10T00:00:00' },
  ],
  experience: [
    {
      title: 'Software Engineer',
      company: 'Acme',
      start_date: '2020-01',
      end_date: 'present',
      description: 'Built things',
      added_at: '2026-02-10T00:00:00',
    },
  ],
  preferences: {
    target_roles: ['Software Engineer', 'SRE'],
    target_locations: ['Seattle', 'Remote'],
    remote_preference: 'remote',
    salary_min: 150000,
    salary_max: 250000,
    job_types: ['full-time'],
    industries: [],
    excluded_companies: ['meta'],
  },
  resume: { summary: '', content: '', last_updated: null },
  notes: 'Some notes',
  is_active: true,
}

describe('ProfileFormPage - Create Mode', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders create form with heading', () => {
    renderCreateMode()
    expect(screen.getByRole('heading', { name: /create profile/i })).toBeInTheDocument()
  })

  it('renders all basic info fields', () => {
    renderCreateMode()
    expect(screen.getByPlaceholderText('City, State')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Any additional notes...')).toBeInTheDocument()
    // Check inputs exist by their labels in the DOM
    expect(screen.getByText('Full Name')).toBeInTheDocument()
    expect(screen.getByText('Email')).toBeInTheDocument()
    expect(screen.getByText('Phone')).toBeInTheDocument()
    expect(screen.getByText('Location')).toBeInTheDocument()
  })

  it('does not show skills or preferences in create mode', () => {
    renderCreateMode()
    expect(screen.queryByText('Skills')).not.toBeInTheDocument()
    expect(screen.queryByText('Job Preferences')).not.toBeInTheDocument()
  })

  it('allows entering basic info fields', async () => {
    renderCreateMode()
    const user = userEvent.setup()

    const locationInput = screen.getByPlaceholderText('City, State')
    await user.type(locationInput, 'Seattle, WA')
    expect(locationInput).toHaveValue('Seattle, WA')

    const notesInput = screen.getByPlaceholderText('Any additional notes...')
    await user.type(notesInput, 'Test notes')
    expect(notesInput).toHaveValue('Test notes')
  })

  it('calls create API on submit', async () => {
    mockCreate.mockResolvedValue({ id: 'test', name: 'Test' })
    renderCreateMode()

    const form = document.querySelector('form')!
    fireEvent.submit(form)

    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledTimes(1)
      // First arg should be the form data object
      const callArg = mockCreate.mock.calls[0][0]
      expect(callArg).toHaveProperty('name')
      expect(callArg).toHaveProperty('email')
      expect(callArg).toHaveProperty('phone')
      expect(callArg).toHaveProperty('location')
    })
  })

  it('navigates to profile on successful create', async () => {
    mockCreate.mockResolvedValue({ id: 'john_doe', name: 'John Doe' })
    renderCreateMode()

    const form = document.querySelector('form')!
    const nameInput = form.querySelector('input[required]') as HTMLInputElement
    fireEvent.change(nameInput, { target: { value: 'John Doe' } })
    fireEvent.submit(form)

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/profiles/john_doe')
    })
  })

  it('shows error message on failed create', async () => {
    mockCreate.mockRejectedValue({
      response: { data: { detail: 'Profile creation failed' } },
    })
    renderCreateMode()

    const form = document.querySelector('form')!
    const nameInput = form.querySelector('input[required]') as HTMLInputElement
    fireEvent.change(nameInput, { target: { value: 'Test' } })
    fireEvent.submit(form)

    await waitFor(() => {
      expect(screen.getByText('Profile creation failed')).toBeInTheDocument()
    })
  })

  it('has cancel button that navigates back', async () => {
    renderCreateMode()
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: /cancel/i }))
    expect(mockNavigate).toHaveBeenCalledWith('/profiles')
  })
})

describe('ProfileFormPage - Edit Mode', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders edit form with heading', async () => {
    renderEditMode(mockProfile)
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /edit profile/i })).toBeInTheDocument()
    })
  })

  it('populates form fields from profile data', async () => {
    renderEditMode(mockProfile)
    await waitFor(() => {
      const form = document.querySelector('form')!
      const inputs = form.querySelectorAll('input')
      const nameInput = inputs[0] as HTMLInputElement
      expect(nameInput.value).toBe('Test User')
    })
  })

  it('shows skills section in edit mode', async () => {
    renderEditMode(mockProfile)
    await waitFor(() => {
      expect(screen.getByText('Skills')).toBeInTheDocument()
    })
    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.getByText('React')).toBeInTheDocument()
  })

  it('shows preferences section in edit mode', async () => {
    renderEditMode(mockProfile)
    await waitFor(() => {
      expect(screen.getByText('Job Preferences')).toBeInTheDocument()
    })
  })

  it('populates comma-separated target roles', async () => {
    renderEditMode(mockProfile)
    await waitFor(() => {
      const rolesInput = screen.getByPlaceholderText('Software Engineer, Developer')
      expect(rolesInput).toHaveValue('Software Engineer, SRE')
    })
  })

  it('populates comma-separated target locations', async () => {
    renderEditMode(mockProfile)
    await waitFor(() => {
      const locInput = screen.getByPlaceholderText('Seattle, Remote')
      expect(locInput).toHaveValue('Seattle, Remote')
    })
  })

  it('populates excluded companies', async () => {
    renderEditMode(mockProfile)
    await waitFor(() => {
      const input = screen.getByPlaceholderText('Companies to exclude from matches')
      expect(input).toHaveValue('meta')
    })
  })

  it('allows typing commas and spaces in comma-separated fields', async () => {
    renderEditMode(mockProfile)
    const user = userEvent.setup()

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Software Engineer, Developer')).toBeInTheDocument()
    })

    const rolesInput = screen.getByPlaceholderText('Software Engineer, Developer')
    await user.clear(rolesInput)
    await user.type(rolesInput, 'Dev, Ops, SRE')

    // Value should be exactly what was typed, not split/rejoined
    expect(rolesInput).toHaveValue('Dev, Ops, SRE')
  })

  it('populates salary fields', async () => {
    renderEditMode(mockProfile)
    await waitFor(() => {
      expect(screen.getByPlaceholderText('Min')).toHaveValue(150000)
    })
    expect(screen.getByPlaceholderText('Max')).toHaveValue(250000)
  })

  it('calls update API on save', async () => {
    mockUpdate.mockResolvedValue(mockProfile)
    renderEditMode(mockProfile)

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /edit profile/i })).toBeInTheDocument()
    })

    const form = document.querySelector('form')!
    fireEvent.submit(form)

    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledWith(
        'test_user',
        expect.objectContaining({
          name: 'Test User',
          skills: expect.any(Array),
          preferences: expect.objectContaining({
            target_roles: expect.any(Array),
          }),
        })
      )
    })
  })

  it('shows success message after save', async () => {
    mockUpdate.mockResolvedValue(mockProfile)
    renderEditMode(mockProfile)

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /edit profile/i })).toBeInTheDocument()
    })

    const form = document.querySelector('form')!
    fireEvent.submit(form)

    await waitFor(() => {
      expect(screen.getByText('Profile saved successfully')).toBeInTheDocument()
    })
  })

  it('shows error message on failed save', async () => {
    mockUpdate.mockRejectedValue({
      response: { data: { detail: 'Update failed' } },
    })
    renderEditMode(mockProfile)

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /edit profile/i })).toBeInTheDocument()
    })

    const form = document.querySelector('form')!
    fireEvent.submit(form)

    await waitFor(() => {
      expect(screen.getByText('Update failed')).toBeInTheDocument()
    })
  })
})

describe('ProfileFormPage - Skills Management', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('displays existing skills with level', async () => {
    renderEditMode(mockProfile)
    await waitFor(() => {
      expect(screen.getByText('Python')).toBeInTheDocument()
    })
    expect(screen.getByText('(advanced)')).toBeInTheDocument()
    expect(screen.getByText('React')).toBeInTheDocument()
    expect(screen.getByText('(intermediate)')).toBeInTheDocument()
  })

  it('can add a new skill', async () => {
    renderEditMode(mockProfile)
    const user = userEvent.setup()

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Skill name')).toBeInTheDocument()
    })

    await user.type(screen.getByPlaceholderText('Skill name'), 'TypeScript')

    // Find the add button (the one with Plus icon in the skills row)
    const skillInput = screen.getByPlaceholderText('Skill name')
    const skillRow = skillInput.closest('.flex.gap-2')!
    const addBtn = skillRow.querySelector('button')!
    await user.click(addBtn)

    await waitFor(() => {
      expect(screen.getByText('TypeScript')).toBeInTheDocument()
    })
  })

  it('clears skill input after adding', async () => {
    renderEditMode(mockProfile)
    const user = userEvent.setup()

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Skill name')).toBeInTheDocument()
    })

    const skillInput = screen.getByPlaceholderText('Skill name')
    await user.type(skillInput, 'Go')

    const skillRow = skillInput.closest('.flex.gap-2')!
    const addBtn = skillRow.querySelector('button')!
    await user.click(addBtn)

    await waitFor(() => {
      expect(skillInput).toHaveValue('')
    })
  })

  it('does not add empty skill', async () => {
    renderEditMode(mockProfile)
    const user = userEvent.setup()

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Skill name')).toBeInTheDocument()
    })

    // Count existing skills
    const before = screen.getAllByText(/\(advanced\)|\(intermediate\)|\(beginner\)|\(expert\)/).length

    const skillInput = screen.getByPlaceholderText('Skill name')
    const skillRow = skillInput.closest('.flex.gap-2')!
    const addBtn = skillRow.querySelector('button')!
    await user.click(addBtn)

    const after = screen.getAllByText(/\(advanced\)|\(intermediate\)|\(beginner\)|\(expert\)/).length
    expect(after).toBe(before)
  })
})

describe('ProfileFormPage - Preferences', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows remote preference dropdown with correct value', async () => {
    renderEditMode(mockProfile)
    await waitFor(() => {
      const select = screen.getByDisplayValue('Remote')
      expect(select).toBeInTheDocument()
    })
  })

  it('can change remote preference', async () => {
    renderEditMode(mockProfile)
    const user = userEvent.setup()

    await waitFor(() => {
      expect(screen.getByDisplayValue('Remote')).toBeInTheDocument()
    })

    const select = screen.getByDisplayValue('Remote')
    await user.selectOptions(select, 'hybrid')
    expect(select).toHaveValue('hybrid')
  })

  it('includes preferences in save payload', async () => {
    mockUpdate.mockResolvedValue(mockProfile)
    renderEditMode(mockProfile)

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /edit profile/i })).toBeInTheDocument()
    })

    const form = document.querySelector('form')!
    fireEvent.submit(form)

    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledWith(
        'test_user',
        expect.objectContaining({
          preferences: expect.objectContaining({
            target_roles: ['Software Engineer', 'SRE'],
            target_locations: ['Seattle', 'Remote'],
            remote_preference: 'remote',
            excluded_companies: ['meta'],
          }),
        })
      )
    })
  })
})
