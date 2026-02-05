import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { profilesApi } from '../api'
import { Plus, User, Check, Trash2 } from 'lucide-react'

export default function ProfilesPage() {
  const queryClient = useQueryClient()

  const { data: profiles, isLoading } = useQuery({
    queryKey: ['profiles'],
    queryFn: profilesApi.list,
  })

  const activateMutation = useMutation({
    mutationFn: profilesApi.activate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: profilesApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profiles'] })
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Profiles</h1>
          <p className="text-gray-600 mt-1">
            Manage your job search profiles
          </p>
        </div>
        <Link to="/profiles/new" className="btn btn-primary flex items-center gap-2">
          <Plus size={20} />
          New Profile
        </Link>
      </div>

      {profiles && profiles.length > 0 ? (
        <div className="grid gap-4">
          {profiles.map((profile) => (
            <div
              key={profile.id}
              className={`card flex items-center justify-between ${
                profile.is_active ? 'ring-2 ring-primary-500' : ''
              }`}
            >
              <div className="flex items-center gap-4">
                <div className={`w-12 h-12 rounded-full flex items-center justify-center ${
                  profile.is_active ? 'bg-primary-100' : 'bg-gray-100'
                }`}>
                  <User className={profile.is_active ? 'text-primary-600' : 'text-gray-500'} size={24} />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <Link
                      to={`/profiles/${profile.id}`}
                      className="font-semibold text-gray-900 hover:text-primary-600"
                    >
                      {profile.name}
                    </Link>
                    {profile.is_active && (
                      <span className="px-2 py-0.5 bg-primary-100 text-primary-700 text-xs rounded-full">
                        Active
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-500">
                    {profile.location || 'No location'} · {profile.skills_count} skills
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                {!profile.is_active && (
                  <button
                    onClick={() => activateMutation.mutate(profile.id)}
                    disabled={activateMutation.isPending}
                    className="btn btn-secondary flex items-center gap-2"
                  >
                    <Check size={16} />
                    Set Active
                  </button>
                )}
                <Link
                  to={`/profiles/${profile.id}`}
                  className="btn btn-secondary"
                >
                  Edit
                </Link>
                <button
                  onClick={() => {
                    if (confirm('Are you sure you want to delete this profile?')) {
                      deleteMutation.mutate(profile.id)
                    }
                  }}
                  disabled={deleteMutation.isPending}
                  className="btn btn-danger flex items-center gap-2"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="card text-center py-12">
          <User className="mx-auto text-gray-400 mb-4" size={48} />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            No profiles yet
          </h3>
          <p className="text-gray-500 mb-4">
            Create your first profile to start searching for jobs
          </p>
          <Link to="/profiles/new" className="btn btn-primary inline-flex items-center gap-2">
            <Plus size={20} />
            Create Profile
          </Link>
        </div>
      )}
    </div>
  )
}
