import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { jobsApi, documentsApi } from '../api'
import { JobStatus } from '../types'
import { DocumentListItem } from '../api/documents'
import {
  ArrowLeft,
  ExternalLink,
  FileText,
  Download,
  Archive,
  Trash2,
  MapPin,
  Building,
  DollarSign,
  Send,
  Phone,
  Award,
  XCircle,
  Save,
  RefreshCw,
} from 'lucide-react'

const STATUS_CONFIG: Record<JobStatus, { label: string; color: string; icon: React.ReactNode }> = {
  active: { label: 'Active', color: 'bg-blue-100 text-blue-700', icon: null },
  applied: { label: 'Applied', color: 'bg-indigo-100 text-indigo-700', icon: <Send size={14} /> },
  interviewing: { label: 'Interviewing', color: 'bg-amber-100 text-amber-700', icon: <Phone size={14} /> },
  offered: { label: 'Offered', color: 'bg-emerald-100 text-emerald-700', icon: <Award size={14} /> },
  rejected: { label: 'Rejected', color: 'bg-red-100 text-red-700', icon: <XCircle size={14} /> },
  completed: { label: 'Completed', color: 'bg-green-100 text-green-700', icon: null },
  archived: { label: 'Archived', color: 'bg-gray-100 text-gray-700', icon: <Archive size={14} /> },
}

export default function JobDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [isGenerating, setIsGenerating] = useState(false)
  const [generationStatus, setGenerationStatus] = useState('')
  const [editingNotes, setEditingNotes] = useState(false)
  const [notesValue, setNotesValue] = useState('')

  const { data: job, isLoading } = useQuery({
    queryKey: ['job', id],
    queryFn: () => jobsApi.get(id!),
    enabled: !!id,
  })

  // Fetch documents for this job
  const { data: allDocs = [] } = useQuery({
    queryKey: ['documents'],
    queryFn: () => documentsApi.list(),
  })
  const jobDocs = allDocs.filter((d: DocumentListItem) => d.job_id === id)

  const updateMutation = useMutation({
    mutationFn: (data: { status?: JobStatus; notes?: string }) =>
      jobsApi.update(id!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['job', id] })
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => jobsApi.delete(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      navigate('/jobs')
    },
  })

  const handleGenerate = async (type: 'resume' | 'cover_letter' | 'package') => {
    if (!id) return
    setIsGenerating(true)
    const labels = { resume: 'resume', cover_letter: 'cover letter', package: 'resume + cover letter' }
    setGenerationStatus(`Generating ${labels[type]}...`)
    try {
      if (type === 'package') {
        await documentsApi.generatePackage({ job_id: id })
      } else if (type === 'resume') {
        const doc = await documentsApi.generateResume({ job_id: id })
        setGenerationStatus(`Resume generated! Score: ${doc.quality_scores.overall_score}%`)
        try {
          const blob = await documentsApi.download(doc.id)
          const url = window.URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = `resume_${job?.company || 'job'}.pdf`
          a.click()
          window.URL.revokeObjectURL(url)
        } catch { /* PDF may not exist yet */ }
        queryClient.invalidateQueries({ queryKey: ['documents'] })
        return
      } else {
        const doc = await documentsApi.generateCoverLetter({ job_id: id })
        setGenerationStatus(`Cover letter generated! Score: ${doc.quality_scores.overall_score}%`)
        try {
          const blob = await documentsApi.download(doc.id)
          const url = window.URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = `cover_letter_${job?.company || 'job'}.pdf`
          a.click()
          window.URL.revokeObjectURL(url)
        } catch { /* PDF may not exist yet */ }
        queryClient.invalidateQueries({ queryKey: ['documents'] })
        return
      }
      setGenerationStatus('Documents generated successfully!')
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      const msg = error?.response?.data?.detail || ''
      if (msg.toLowerCase().includes('ollama') || msg.toLowerCase().includes('connection')) {
        setGenerationStatus('Document generation is temporarily unavailable. The AI service needs to be configured by the administrator.')
      } else {
        setGenerationStatus(msg || 'Generation failed. Make sure you have an active profile set up.')
      }
    } finally {
      setIsGenerating(false)
    }
  }

  const handleDownloadDoc = async (doc: DocumentListItem) => {
    try {
      const blob = await documentsApi.download(doc.id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${doc.job_company}_${doc.document_type}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch { /* ignore */ }
  }

  const handleSaveNotes = () => {
    updateMutation.mutate({ notes: notesValue })
    setEditingNotes(false)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (!job) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold text-gray-900">Job not found</h2>
        <button onClick={() => navigate('/jobs')} className="btn btn-primary mt-4">
          Back to Jobs
        </button>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <button
          onClick={() => navigate('/jobs')}
          className="p-2 hover:bg-gray-100 rounded-lg"
        >
          <ArrowLeft size={20} />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-2xl font-bold text-gray-900">{job.title}</h1>
            {job.match && (
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                job.match.combined_score >= 80
                  ? 'bg-green-100 text-green-700'
                  : job.match.combined_score >= 60
                  ? 'bg-yellow-100 text-yellow-700'
                  : 'bg-gray-100 text-gray-700'
              }`}>
                {job.match.combined_score}% match
              </span>
            )}
          </div>
          <div className="flex items-center gap-4 text-gray-600">
            <span className="flex items-center gap-1">
              <Building size={16} />
              {job.company}
            </span>
            <span className="flex items-center gap-1">
              <MapPin size={16} />
              {job.location}
            </span>
            {job.salary && job.salary !== 'Not specified' && (
              <span className="flex items-center gap-1">
                <DollarSign size={16} />
                {job.salary}
              </span>
            )}
          </div>
        </div>
        {job.url && (
          <a
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-secondary flex items-center gap-2"
          >
            <ExternalLink size={18} />
            View Original
          </a>
        )}
      </div>

      {/* Application Status Tracker */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-3">Application Status</h2>
        <div className="flex flex-wrap items-center gap-2">
          {(Object.entries(STATUS_CONFIG) as [JobStatus, typeof STATUS_CONFIG[JobStatus]][]).map(([key, cfg]) => (
            <button
              key={key}
              onClick={() => updateMutation.mutate({ status: key })}
              disabled={updateMutation.isPending}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
                job.status === key
                  ? `${cfg.color} ring-2 ring-offset-1 ring-current`
                  : 'bg-gray-50 text-gray-400 hover:bg-gray-100 hover:text-gray-600'
              }`}
            >
              {cfg.icon}
              {cfg.label}
            </button>
          ))}
        </div>

        {/* Notes */}
        <div className="mt-4 pt-4 border-t border-gray-100">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-700">Notes</span>
            {!editingNotes && (
              <button
                onClick={() => { setNotesValue(job.notes || ''); setEditingNotes(true) }}
                className="text-xs text-primary-600 hover:text-primary-700"
              >
                Edit
              </button>
            )}
          </div>
          {editingNotes ? (
            <div className="space-y-2">
              <textarea
                value={notesValue}
                onChange={(e) => setNotesValue(e.target.value)}
                rows={3}
                className="input w-full"
                placeholder="Add notes about this application..."
              />
              <div className="flex gap-2">
                <button onClick={handleSaveNotes} className="btn btn-primary btn-sm flex items-center gap-1">
                  <Save size={14} />
                  Save
                </button>
                <button onClick={() => setEditingNotes(false)} className="btn btn-secondary btn-sm">
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-500 italic">
              {job.notes || 'No notes yet. Click Edit to add.'}
            </p>
          )}
        </div>
      </div>

      {/* Document Generation */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Generate Documents</h2>
        <div className="flex items-center gap-3">
          <button
            onClick={() => handleGenerate('package')}
            disabled={isGenerating}
            className="btn btn-primary flex items-center gap-2"
          >
            <FileText size={18} />
            {isGenerating ? 'Generating...' : 'Resume + Cover Letter'}
          </button>
          <button
            onClick={() => handleGenerate('resume')}
            disabled={isGenerating}
            className="btn btn-secondary flex items-center gap-2"
          >
            Resume Only
          </button>
          <button
            onClick={() => handleGenerate('cover_letter')}
            disabled={isGenerating}
            className="btn btn-secondary flex items-center gap-2"
          >
            Cover Letter Only
          </button>
        </div>
        {generationStatus && (
          <p className={`mt-3 text-sm ${
            generationStatus.includes('failed') || generationStatus.includes('Failed')
              ? 'text-red-600' : 'text-gray-600'
          }`}>
            {generationStatus}
          </p>
        )}

        {/* Existing documents for this job */}
        {jobDocs.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-100">
            <h3 className="text-sm font-medium text-gray-700 mb-2">
              Generated Documents ({jobDocs.length})
            </h3>
            <div className="space-y-2">
              {jobDocs.map((doc: DocumentListItem) => (
                <div key={doc.id} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-2">
                    <FileText size={16} className={doc.document_type === 'resume' ? 'text-blue-500' : 'text-purple-500'} />
                    <span className="text-sm font-medium">
                      {doc.document_type === 'resume' ? 'Resume' : 'Cover Letter'}
                    </span>
                    {doc.overall_score > 0 && (
                      <span className="text-xs bg-gray-200 px-1.5 py-0.5 rounded">
                        {doc.overall_score.toFixed(0)}%
                      </span>
                    )}
                    <span className="text-xs text-gray-400">
                      {new Date(doc.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => handleGenerate(doc.document_type === 'resume' ? 'resume' : 'cover_letter')}
                      disabled={isGenerating}
                      className="p-1.5 text-gray-400 hover:text-primary-600 rounded"
                      title="Regenerate"
                    >
                      <RefreshCw size={14} />
                    </button>
                    {doc.pdf_path && (
                      <button
                        onClick={() => handleDownloadDoc(doc)}
                        className="p-1.5 text-gray-400 hover:text-primary-600 rounded"
                        title="Download PDF"
                      >
                        <Download size={14} />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Match Details */}
      {job.match && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-2">Match Analysis</h2>
          <p className="text-sm text-gray-500 mb-4">
            {job.match.combined_score >= 80
              ? 'Strong match — this job aligns well with your skills and experience.'
              : job.match.combined_score >= 60
              ? 'Good match — you meet many of the requirements for this role.'
              : 'Partial match — some of your skills align, but there may be gaps.'}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <p className="text-2xl font-bold text-primary-600">
                {job.match.keyword_score}%
              </p>
              <p className="text-sm text-gray-500">Skills Match</p>
            </div>
            {job.match.llm_score !== null && job.match.llm_score !== undefined && (
              <div className="text-center p-4 bg-gray-50 rounded-lg">
                <p className="text-2xl font-bold text-primary-600">
                  {job.match.llm_score}%
                </p>
                <p className="text-sm text-gray-500">Overall Fit</p>
              </div>
            )}
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <p className="text-2xl font-bold text-primary-600">
                {job.match.combined_score}%
              </p>
              <p className="text-sm text-gray-500">Combined Score</p>
            </div>
          </div>
        </div>
      )}

      {/* Description */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Job Description</h2>
        <div className="prose prose-sm max-w-none text-gray-700 whitespace-pre-wrap">
          {job.description || 'No description available'}
        </div>
      </div>

      {/* Metadata + Danger Zone */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Details</h2>
        <dl className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-gray-500">Source</dt>
            <dd className="font-medium capitalize">{job.platform}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Added Via</dt>
            <dd className="font-medium capitalize">{job.added_by}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Posted Date</dt>
            <dd className="font-medium">{job.posted_date || 'Unknown'}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Added On</dt>
            <dd className="font-medium">
              {new Date(job.cached_at).toLocaleDateString()}
            </dd>
          </div>
        </dl>
        <div className="mt-4 pt-4 border-t border-gray-100 flex justify-end">
          <button
            onClick={() => {
              if (confirm('Are you sure you want to delete this job?')) {
                deleteMutation.mutate()
              }
            }}
            className="btn btn-danger flex items-center gap-2"
          >
            <Trash2 size={16} />
            Delete Job
          </button>
        </div>
      </div>
    </div>
  )
}
