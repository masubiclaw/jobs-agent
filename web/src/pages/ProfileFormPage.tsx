import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { profilesApi } from '../api'
import { Profile, ProfileUpdate, Skill, Experience, Preferences } from '../types'
import { ArrowLeft, Plus, Trash2, Save } from 'lucide-react'

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
    }
  }, [profile])

  const createMutation = useMutation({
    mutationFn: profilesApi.create,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] })
      navigate(`/profiles/${data.id}`)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: ProfileUpdate }) =>
      profilesApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] })
      queryClient.invalidateQueries({ queryKey: ['profile', id] })
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    if (isEditing) {
      updateMutation.mutate({
        id: id!,
        data: {
          ...formData,
          skills,
          experience,
          preferences,
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

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Basic Info */}
        <div className="card space-y-4">
          <h2 className="text-lg font-semibold">Basic Information</h2>

          <div className="grid grid-cols-2 gap-4">
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

        {/* Preferences */}
        {isEditing && (
          <div className="card space-y-4">
            <h2 className="text-lg font-semibold">Job Preferences</h2>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Target Roles (comma-separated)</label>
                <input
                  type="text"
                  value={preferences.target_roles.join(', ')}
                  onChange={(e) =>
                    setPreferences({
                      ...preferences,
                      target_roles: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                    })
                  }
                  className="input"
                  placeholder="Software Engineer, Developer"
                />
              </div>
              <div>
                <label className="label">Target Locations (comma-separated)</label>
                <input
                  type="text"
                  value={preferences.target_locations.join(', ')}
                  onChange={(e) =>
                    setPreferences({
                      ...preferences,
                      target_locations: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                    })
                  }
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
                value={preferences.excluded_companies.join(', ')}
                onChange={(e) =>
                  setPreferences({
                    ...preferences,
                    excluded_companies: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                  })
                }
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
