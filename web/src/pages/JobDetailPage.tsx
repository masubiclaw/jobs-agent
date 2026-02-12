import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { jobsApi, documentsApi } from '../api'
import { JobStatus } from '../types'
import { 
  ArrowLeft, 
  ExternalLink, 
  FileText, 
  Download, 
  Check, 
  Archive,
  Trash2,
  MapPin,
  Building,
  DollarSign,
  Calendar
} from 'lucide-react'

export default function JobDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [isGenerating, setIsGenerating] = useState(false)
  const [generationStatus, setGenerationStatus] = useState('')

  const { data: job, isLoading } = useQuery({
    queryKey: ['job', id],
    queryFn: () => jobsApi.get(id!),
    enabled: !!id,
  })

  const updateMutation = useMutation({
    mutationFn: ({ status }: { status: JobStatus }) =>
      jobsApi.update(id!, { status }),
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

  const handleGenerateResume = async () => {
    if (!id) return
    setIsGenerating(true)
    setGenerationStatus('Generating resume...')
    try {
      const doc = await documentsApi.generateResume({ job_id: id })
      setGenerationStatus(`Resume generated! Score: ${doc.quality_scores.overall_score}%`)

      // Download the PDF
      try {
        const blob = await documentsApi.download(doc.id)
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `resume_${job?.company || 'job'}.pdf`
        a.click()
        window.URL.revokeObjectURL(url)
      } catch {
        // PDF download may fail, but document was still generated
      }
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      const detail = error?.response?.data?.detail || 'Failed to generate resume. Check that you have an active profile and Ollama is running.'
      setGenerationStatus(detail)
    } finally {
      setIsGenerating(false)
    }
  }

  const handleGenerateCoverLetter = async () => {
    if (!id) return
    setIsGenerating(true)
    setGenerationStatus('Generating cover letter...')
    try {
      const doc = await documentsApi.generateCoverLetter({ job_id: id })
      setGenerationStatus(`Cover letter generated! Score: ${doc.quality_scores.overall_score}%`)

      // Download the PDF
      try {
        const blob = await documentsApi.download(doc.id)
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `cover_letter_${job?.company || 'job'}.pdf`
        a.click()
        window.URL.revokeObjectURL(url)
      } catch {
        // PDF download may fail, but document was still generated
      }
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      const detail = error?.response?.data?.detail || 'Failed to generate cover letter. Check that you have an active profile and Ollama is running.'
      setGenerationStatus(detail)
    } finally {
      setIsGenerating(false)
    }
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

      {/* Status and Actions */}
      <div className="card">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-500">Status:</span>
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${
              job.status === 'active'
                ? 'bg-blue-100 text-blue-700'
                : job.status === 'completed'
                ? 'bg-green-100 text-green-700'
                : 'bg-gray-100 text-gray-700'
            }`}>
              {job.status}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {job.status !== 'completed' && (
              <button
                onClick={() => updateMutation.mutate({ status: 'completed' })}
                className="btn btn-secondary flex items-center gap-2"
              >
                <Check size={16} />
                Mark Completed
              </button>
            )}
            {job.status !== 'archived' && (
              <button
                onClick={() => updateMutation.mutate({ status: 'archived' })}
                className="btn btn-secondary flex items-center gap-2"
              >
                <Archive size={16} />
                Archive
              </button>
            )}
            <button
              onClick={() => {
                if (confirm('Are you sure you want to delete this job?')) {
                  deleteMutation.mutate()
                }
              }}
              className="btn btn-danger flex items-center gap-2"
            >
              <Trash2 size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* Document Generation */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Generate Documents</h2>
        <div className="flex items-center gap-4">
          <button
            onClick={handleGenerateResume}
            disabled={isGenerating}
            className="btn btn-primary flex items-center gap-2"
          >
            <FileText size={18} />
            Generate Resume
          </button>
          <button
            onClick={handleGenerateCoverLetter}
            disabled={isGenerating}
            className="btn btn-secondary flex items-center gap-2"
          >
            <FileText size={18} />
            Generate Cover Letter
          </button>
        </div>
        {generationStatus && (
          <p className="mt-4 text-sm text-gray-600">{generationStatus}</p>
        )}
      </div>

      {/* Match Details */}
      {job.match && (
        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Match Analysis</h2>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <p className="text-2xl font-bold text-primary-600">
                {job.match.keyword_score}%
              </p>
              <p className="text-sm text-gray-500">Keyword Score</p>
            </div>
            {job.match.llm_score !== null && job.match.llm_score !== undefined && (
              <div className="text-center p-4 bg-gray-50 rounded-lg">
                <p className="text-2xl font-bold text-primary-600">
                  {job.match.llm_score}%
                </p>
                <p className="text-sm text-gray-500">LLM Score</p>
              </div>
            )}
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <p className="text-2xl font-bold text-primary-600">
                {job.match.combined_score}%
              </p>
              <p className="text-sm text-gray-500">Combined Score</p>
            </div>
          </div>
          <p className="text-sm text-gray-500">
            Match Level: <span className="font-medium">{job.match.match_level}</span>
          </p>
        </div>
      )}

      {/* Description */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Job Description</h2>
        <div className="prose prose-sm max-w-none">
          <pre className="whitespace-pre-wrap font-sans text-gray-700">
            {job.description || 'No description available'}
          </pre>
        </div>
      </div>

      {/* Metadata */}
      <div className="card">
        <h2 className="text-lg font-semibold mb-4">Details</h2>
        <dl className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-gray-500">Platform</dt>
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
            <dt className="text-gray-500">Cached At</dt>
            <dd className="font-medium">
              {new Date(job.cached_at).toLocaleDateString()}
            </dd>
          </div>
        </dl>
      </div>
    </div>
  )
}
