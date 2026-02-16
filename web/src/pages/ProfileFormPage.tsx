import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { profilesApi } from '../api'
import { Profile, ProfileUpdate, Skill, Experience, Preferences } from '../types'
import { ArrowLeft, Plus, Trash2, Save, CheckCircle, AlertCircle } from 'lucide-react'

export default function ProfileFormPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const isEditing = !!id

  const { data: profile, isLoading } = useQuery({
    queryKey: ['profile', id],
    queryFn: () => profilesApi.get(id!),
    enabled: isEditing,
  })

  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    location: '',
    notes: '',
  })

  const [skills, setSkills] = useState<Skill[]>([])
  const [newSkill, setNewSkill] = useState({ name: '', level: 'intermediate' as const })

  const [experience, setExperience] = useState<Experience[]>([])
  const [newExp, setNewExp] = useState({ title: '', company: '', start_date: '', end_date: '', description: '' })

  const [preferences, setPreferences] = useState<Preferences>({
    target_roles: [],
    target_locations: [],
    remote_preference: 'hybrid',
    salary_min: undefined,
    salary_max: undefined,
    job_types: ['full-time'],
    industries: [],
    excluded_companies: [],
  })

  // Raw string state for comma-separated fields (split on blur, not on every keystroke)
  const [saveMessage, setSaveMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const showSaveMessage = (type: 'success' | 'error', text: string) => {
    setSaveMessage({ type, text })
    setTimeout(() => setSaveMessage(null), 5000)
  }

  const [rawTargetRoles, setRawTargetRoles] = useState('')
  const [rawTargetLocations, setRawTargetLocations] = useState('')
  const [rawExcludedCompanies, setRawExcludedCompanies] = useState('')

  const splitCsv = (val: string) => val.split(',').map(s => s.trim()).filter(Boolean)

  useEffect(() => {
    if (profile) {
      setFormData({
        name: profile.name,
        email: profile.email,
        phone: profile.phone,
        location: profile.location,
        notes: profile.notes,
      })
      setSkills(profile.skills)
      setExperience(profile.experience)
      setPreferences(profile.preferences)
      setRawTargetRoles(profile.preferences.target_roles.join(', '))
      setRawTargetLocations(profile.preferences.target_locations.join(', '))
      setRawExcludedCompanies(profile.preferences.excluded_companies.join(', '))
    }
  }, [profile])

  const createMutation = useMutation({
    mutationFn: profilesApi.create,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] })
      navigate(`/profiles/${data.id}`)
    },
    onError: (err: any) => {
      showSaveMessage('error', err?.response?.data?.detail || 'Failed to create profile')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: ProfileUpdate }) =>
      profilesApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] })
      queryClient.invalidateQueries({ queryKey: ['profile', id] })
      showSaveMessage('success', 'Profile saved successfully')
    },
    onError: (err: any) => {
      showSaveMessage('error', err?.response?.data?.detail || 'Failed to save profile')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    const finalPreferences = {
      ...preferences,
      target_roles: splitCsv(rawTargetRoles),
      target_locations: splitCsv(rawTargetLocations),
      excluded_companies: splitCsv(rawExcludedCompanies),
    }

    if (isEditing) {
      updateMutation.mutate({
        id: id!,
        data: {
          ...formData,
          skills,
          experience,
          preferences: finalPreferences,
        },
      })
    } else {
      createMutation.mutate(formData)
    }
  }

  const addSkill = () => {
    if (newSkill.name.trim()) {
      setSkills([...skills, { ...newSkill, added_at: new Date().toISOString() }])
      setNewSkill({ name: '', level: 'intermediate' })
    }
  }

  const removeSkill = (index: number) => {
    setSkills(skills.filter((_, i) => i !== index))
  }

  const addExperience = () => {
    if (newExp.title.trim() && newExp.company.trim()) {
      setExperience([...experience, { ...newExp, added_at: new Date().toISOString() }])
      setNewExp({ title: '', company: '', start_date: '', end_date: '', description: '' })
    }
  }

  const removeExperience = (index: number) => {
    setExperience(experience.filter((_, i) => i !== index))
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate('/profiles')}
          className="p-2 hover:bg-gray-100 rounded-lg"
        >
          <ArrowLeft size={20} />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {isEditing ? 'Edit Profile' : 'Create Profile'}
          </h1>
          <p className="text-gray-600 mt-1">
            {isEditing
              ? 'Update your profile information'
              : 'Fill in your details to create a new profile'}
          </p>
        </div>
      </div>

      {saveMessage && (
        <div
          className={`p-3 rounded-lg flex items-center gap-2 ${
            saveMessage.type === 'success'
              ? 'bg-green-50 text-green-700 border border-green-200'
              : 'bg-red-50 text-red-700 border border-red-200'
          }`}
        >
          {saveMessage.type === 'success' ? <CheckCircle size={20} /> : <AlertCircle size={20} />}
          <span className="text-sm">{saveMessage.text}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Basic Info */}
        <div className="card space-y-4">
          <h2 className="text-lg font-semibold">Basic Information</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Full Name</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="input"
                required
              />
            </div>
            <div>
              <label className="label">Email</label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="input"
              />
            </div>
            <div>
              <label className="label">Phone</label>
              <input
                type="tel"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                className="input"
              />
            </div>
            <div>
              <label className="label">Location</label>
              <input
                type="text"
                value={formData.location}
                onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                className="input"
                placeholder="City, State"
              />
            </div>
          </div>

          <div>
            <label className="label">Notes</label>
            <textarea
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              className="input"
              rows={3}
              placeholder="Any additional notes..."
            />
          </div>
        </div>

        {/* Skills */}
        {isEditing && (
          <div className="card space-y-4">
            <h2 className="text-lg font-semibold">Skills</h2>

            <div className="flex gap-2">
              <input
                type="text"
                value={newSkill.name}
                onChange={(e) => setNewSkill({ ...newSkill, name: e.target.value })}
                className="input flex-1"
                placeholder="Skill name"
              />
              <select
                value={newSkill.level}
                onChange={(e) => setNewSkill({ ...newSkill, level: e.target.value as Skill['level'] })}
                className="input w-40"
              >
                <option value="beginner">Beginner</option>
                <option value="intermediate">Intermediate</option>
                <option value="advanced">Advanced</option>
                <option value="expert">Expert</option>
              </select>
              <button type="button" onClick={addSkill} className="btn btn-secondary">
                <Plus size={20} />
              </button>
            </div>

            <div className="flex flex-wrap gap-2">
              {skills.map((skill, index) => (
                <div
                  key={index}
                  className="flex items-center gap-2 px-3 py-1 bg-gray-100 rounded-full"
                >
                  <span>{skill.name}</span>
                  <span className="text-xs text-gray-500">({skill.level})</span>
                  <button
                    type="button"
                    onClick={() => removeSkill(index)}
                    className="text-gray-400 hover:text-red-500"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Experience */}
        {isEditing && (
          <div className="card space-y-4">
            <h2 className="text-lg font-semibold">Experience</h2>

            <div className="space-y-3">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                <input
                  type="text"
                  value={newExp.title}
                  onChange={(e) => setNewExp({ ...newExp, title: e.target.value })}
                  className="input"
                  placeholder="Job Title"
                />
                <input
                  type="text"
                  value={newExp.company}
                  onChange={(e) => setNewExp({ ...newExp, company: e.target.value })}
                  className="input"
                  placeholder="Company"
                />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <input
                  type="text"
                  value={newExp.start_date}
                  onChange={(e) => setNewExp({ ...newExp, start_date: e.target.value })}
                  className="input"
                  placeholder="Start (e.g. 2020-01)"
                />
                <input
                  type="text"
                  value={newExp.end_date}
                  onChange={(e) => setNewExp({ ...newExp, end_date: e.target.value })}
                  className="input"
                  placeholder="End (or present)"
                />
                <button type="button" onClick={addExperience} className="btn btn-secondary flex items-center gap-1">
                  <Plus size={16} /> Add
                </button>
              </div>
              <textarea
                value={newExp.description}
                onChange={(e) => setNewExp({ ...newExp, description: e.target.value })}
                className="input"
                rows={2}
                placeholder="Description (optional)"
              />
            </div>

            {experience.length > 0 && (
              <div className="space-y-2">
                {experience.map((exp, index) => (
                  <div key={index} className="flex items-start justify-between p-3 bg-gray-50 rounded-lg">
                    <div>
                      <div className="font-medium">{exp.title}</div>
                      <div className="text-sm text-gray-600">{exp.company}</div>
                      <div className="text-xs text-gray-400">{exp.start_date} — {exp.end_date || 'present'}</div>
                      {exp.description && <div className="text-sm text-gray-500 mt-1">{exp.description}</div>}
                    </div>
                    <button type="button" onClick={() => removeExperience(index)} className="text-gray-400 hover:text-red-500 ml-2">
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Preferences */}
        {isEditing && (
          <div className="card space-y-4">
            <h2 className="text-lg font-semibold">Job Preferences</h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="label">Target Roles (comma-separated)</label>
                <input
                  type="text"
                  value={rawTargetRoles}
                  onChange={(e) => setRawTargetRoles(e.target.value)}
                  onBlur={() => setPreferences({ ...preferences, target_roles: splitCsv(rawTargetRoles) })}
                  className="input"
                  placeholder="Software Engineer, Developer"
                />
              </div>
              <div>
                <label className="label">Target Locations (comma-separated)</label>
                <input
                  type="text"
                  value={rawTargetLocations}
                  onChange={(e) => setRawTargetLocations(e.target.value)}
                  onBlur={() => setPreferences({ ...preferences, target_locations: splitCsv(rawTargetLocations) })}
                  className="input"
                  placeholder="Seattle, Remote"
                />
              </div>
              <div>
                <label className="label">Remote Preference</label>
                <select
                  value={preferences.remote_preference}
                  onChange={(e) =>
                    setPreferences({
                      ...preferences,
                      remote_preference: e.target.value as Preferences['remote_preference'],
                    })
                  }
                  className="input"
                >
                  <option value="remote">Remote</option>
                  <option value="hybrid">Hybrid</option>
                  <option value="onsite">On-site</option>
                </select>
              </div>
              <div>
                <label className="label">Salary Range</label>
                <div className="flex gap-2">
                  <input
                    type="number"
                    value={preferences.salary_min || ''}
                    onChange={(e) =>
                      setPreferences({
                        ...preferences,
                        salary_min: e.target.value ? parseInt(e.target.value) : undefined,
                      })
                    }
                    className="input"
                    placeholder="Min"
                  />
                  <input
                    type="number"
                    value={preferences.salary_max || ''}
                    onChange={(e) =>
                      setPreferences({
                        ...preferences,
                        salary_max: e.target.value ? parseInt(e.target.value) : undefined,
                      })
                    }
                    className="input"
                    placeholder="Max"
                  />
                </div>
              </div>
            </div>

            <div>
              <label className="label">Excluded Companies (comma-separated)</label>
              <input
                type="text"
                value={rawExcludedCompanies}
                onChange={(e) => setRawExcludedCompanies(e.target.value)}
                onBlur={() => setPreferences({ ...preferences, excluded_companies: splitCsv(rawExcludedCompanies) })}
                className="input"
                placeholder="Companies to exclude from matches"
              />
            </div>
          </div>
        )}

        {/* Submit */}
        <div className="flex justify-end gap-4">
          <button
            type="button"
            onClick={() => navigate('/profiles')}
            className="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={createMutation.isPending || updateMutation.isPending}
            className="btn btn-primary flex items-center gap-2"
          >
            <Save size={20} />
            {isEditing ? 'Save Changes' : 'Create Profile'}
          </button>
        </div>
      </form>
    </div>
  )
}
