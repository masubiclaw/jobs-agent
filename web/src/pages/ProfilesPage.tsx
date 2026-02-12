import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { profilesApi } from '../api'
import {
  Plus, User, Check, Trash2, Upload, Linkedin,
  CheckCircle, AlertCircle, FileText,
} from 'lucide-react'

export default function ProfilesPage() {
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [linkedInUrl, setLinkedInUrl] = useState('')
  const [importTab, setImportTab] = useState<'pdf' | 'linkedin'>('pdf')
  const [importMessage, setImportMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const showMessage = (type: 'success' | 'error', text: string) => {
    setImportMessage({ type, text })
    setTimeout(() => setImportMessage(null), 8000)
  }

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

  const pdfMutation = useMutation({
    mutationFn: profilesApi.importPdf,
    onSuccess: (profile) => {
      showMessage('success', `Profile "${profile.name}" imported from PDF with ${profile.skills.length} skills and ${profile.experience.length} experiences`)
      queryClient.invalidateQueries({ queryKey: ['profiles'] })
      if (fileInputRef.current) fileInputRef.current.value = ''
    },
    onError: (err: any) => {
      showMessage('error', err?.response?.data?.detail || 'Failed to import PDF. Make sure Ollama is running.')
    },
  })

  const linkedInMutation = useMutation({
    mutationFn: profilesApi.importLinkedIn,
    onSuccess: (profile) => {
      showMessage('success', `Profile "${profile.name}" imported from LinkedIn`)
      queryClient.invalidateQueries({ queryKey: ['profiles'] })
      setLinkedInUrl('')
    },
    onError: (err: any) => {
      showMessage('error', err?.response?.data?.detail || 'Failed to import from LinkedIn. Try downloading your profile as PDF instead.')
    },
  })

  const handlePdfUpload = () => {
    const file = fileInputRef.current?.files?.[0]
    if (file) pdfMutation.mutate(file)
  }

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

      {/* Import Profile */}
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <Upload className="text-primary-600" size={24} />
          <h2 className="text-lg font-semibold">Import Profile</h2>
        </div>

        {importMessage && (
          <div
            className={`p-3 rounded-lg flex items-center gap-2 mb-4 ${
              importMessage.type === 'success'
                ? 'bg-green-50 text-green-700 border border-green-200'
                : 'bg-red-50 text-red-700 border border-red-200'
            }`}
          >
            {importMessage.type === 'success' ? <CheckCircle size={20} /> : <AlertCircle size={20} />}
            <span className="text-sm">{importMessage.text}</span>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 mb-4">
          <button
            onClick={() => setImportTab('pdf')}
            className={`px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 ${
              importTab === 'pdf'
                ? 'bg-primary-50 text-primary-700 border border-primary-200'
                : 'text-gray-500 hover:bg-gray-50'
            }`}
          >
            <FileText size={16} />
            PDF Resume
          </button>
          <button
            onClick={() => setImportTab('linkedin')}
            className={`px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 ${
              importTab === 'linkedin'
                ? 'bg-primary-50 text-primary-700 border border-primary-200'
                : 'text-gray-500 hover:bg-gray-50'
            }`}
          >
            <Linkedin size={16} />
            LinkedIn
          </button>
        </div>

        {importTab === 'pdf' ? (
          <div className="flex items-end gap-4">
            <div className="flex-1">
              <label className="label">Resume PDF</label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                className="input py-1.5 text-sm"
              />
            </div>
            <button
              onClick={handlePdfUpload}
              disabled={pdfMutation.isPending}
              className="btn btn-primary whitespace-nowrap"
            >
              {pdfMutation.isPending ? 'Parsing...' : 'Upload & Import'}
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="flex items-end gap-4">
              <div className="flex-1">
                <label className="label">LinkedIn Profile URL</label>
                <input
                  type="url"
                  value={linkedInUrl}
                  onChange={(e) => setLinkedInUrl(e.target.value)}
                  className="input"
                  placeholder="https://linkedin.com/in/username"
                />
              </div>
              <button
                onClick={() => linkedInMutation.mutate(linkedInUrl)}
                disabled={linkedInMutation.isPending || !linkedInUrl.includes('linkedin.com/in/')}
                className="btn btn-primary whitespace-nowrap"
              >
                {linkedInMutation.isPending ? 'Importing...' : 'Import'}
              </button>
            </div>
            <p className="text-xs text-gray-400">
              If LinkedIn blocks access, download your profile as PDF (LinkedIn &gt; More &gt; Save to PDF) and use the PDF tab.
            </p>
          </div>
        )}

        {(pdfMutation.isPending || linkedInMutation.isPending) && (
          <div className="mt-3 flex items-center gap-2 text-sm text-gray-500">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary-600" />
            Parsing with AI... this may take up to 2 minutes.
          </div>
        )}
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
