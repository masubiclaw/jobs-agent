import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { documentsApi, DocumentListItem } from '../api/documents'
import { jobsApi } from '../api/jobs'
import { Job } from '../types'
import {
  FileText,
  Download,
  ExternalLink,
  ThumbsUp,
  ThumbsDown,
  CheckSquare,
  Square,
  Filter,
  Plus,
  CheckCircle,
  AlertCircle,
} from 'lucide-react'

type FilterType = 'all' | 'resume' | 'cover_letter'
type ReviewFilter = 'all' | 'reviewed' | 'unreviewed'
type GenType = 'resume' | 'cover_letter' | 'package'

export default function DocumentsPage() {
  const queryClient = useQueryClient()
  const [typeFilter, setTypeFilter] = useState<FilterType>('all')
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>('all')
  const [selectedJobId, setSelectedJobId] = useState('')
  const [genType, setGenType] = useState<GenType>('package')
  const [genMessage, setGenMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const { data: documents = [], isLoading } = useQuery({
    queryKey: ['documents'],
    queryFn: () => documentsApi.list(),
  })

  const { data: topJobs = [] } = useQuery({
    queryKey: ['top-jobs-for-gen'],
    queryFn: async () => {
      // Try top-matched jobs first, fall back to all jobs
      const top = await jobsApi.getTop(50, 0)
      if (top.length > 0) return top
      const all = await jobsApi.list({ page_size: 100 })
      return all.jobs
    },
  })

  const generateMutation = useMutation({
    mutationFn: async () => {
      if (genType === 'package') {
        return documentsApi.generatePackage({ job_id: selectedJobId })
      } else if (genType === 'resume') {
        return documentsApi.generateResume({ job_id: selectedJobId })
      } else {
        return documentsApi.generateCoverLetter({ job_id: selectedJobId })
      }
    },
    onSuccess: () => {
      setGenMessage({ type: 'success', text: 'Documents generated successfully!' })
      queryClient.invalidateQueries({ queryKey: ['documents'] })
      setTimeout(() => setGenMessage(null), 5000)
    },
    onError: () => {
      setGenMessage({ type: 'error', text: 'Failed to generate documents. Check that you have an active profile.' })
      setTimeout(() => setGenMessage(null), 5000)
    },
  })

  const reviewMutation = useMutation({
    mutationFn: ({ docId, reviewed, is_good }: { docId: string; reviewed?: boolean; is_good?: boolean | null }) =>
      documentsApi.updateReview(docId, reviewed, is_good),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['documents'] }),
  })

  const handleDownload = async (doc: DocumentListItem) => {
    try {
      const blob = await documentsApi.download(doc.id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${doc.job_company}_${doc.document_type}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      // PDF may not exist
    }
  }

  const filtered = documents.filter((doc) => {
    if (typeFilter !== 'all' && doc.document_type !== typeFilter) return false
    if (reviewFilter === 'reviewed' && !doc.reviewed) return false
    if (reviewFilter === 'unreviewed' && doc.reviewed) return false
    return true
  })

  const formatDate = (iso: string) => {
    if (!iso) return ''
    return new Date(iso).toLocaleDateString()
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Documents</h1>
        <p className="text-gray-600 mt-1">Generated resumes and cover letters</p>
      </div>

      {/* Generate Documents */}
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <Plus className="text-primary-600" size={24} />
          <h2 className="text-lg font-semibold">Generate Documents</h2>
        </div>

        {genMessage && (
          <div
            className={`p-3 rounded-lg flex items-center gap-2 mb-4 ${
              genMessage.type === 'success'
                ? 'bg-green-50 text-green-700 border border-green-200'
                : 'bg-red-50 text-red-700 border border-red-200'
            }`}
          >
            {genMessage.type === 'success' ? <CheckCircle size={20} /> : <AlertCircle size={20} />}
            {genMessage.text}
          </div>
        )}

        <div className="flex items-end gap-4">
          <div className="flex-1">
            <label className="label">Job</label>
            <select
              value={selectedJobId}
              onChange={(e) => setSelectedJobId(e.target.value)}
              className="input"
            >
              <option value="">Select a job...</option>
              {topJobs.map((job: Job) => (
                <option key={job.id} value={job.id}>
                  {job.title} - {job.company}
                  {job.match ? ` (${job.match.combined_score}%)` : ''}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Type</label>
            <select
              value={genType}
              onChange={(e) => setGenType(e.target.value as GenType)}
              className="input"
            >
              <option value="package">Both (Resume + Cover Letter)</option>
              <option value="resume">Resume Only</option>
              <option value="cover_letter">Cover Letter Only</option>
            </select>
          </div>
          <button
            onClick={() => generateMutation.mutate()}
            disabled={!selectedJobId || generateMutation.isPending}
            className="btn btn-primary whitespace-nowrap"
          >
            {generateMutation.isPending ? 'Generating...' : 'Generate'}
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Filter size={16} className="text-gray-400" />
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value as FilterType)}
            className="input py-1.5 text-sm"
          >
            <option value="all">All Types</option>
            <option value="resume">Resumes</option>
            <option value="cover_letter">Cover Letters</option>
          </select>
        </div>
        <select
          value={reviewFilter}
          onChange={(e) => setReviewFilter(e.target.value as ReviewFilter)}
          className="input py-1.5 text-sm"
        >
          <option value="all">All Status</option>
          <option value="reviewed">Reviewed</option>
          <option value="unreviewed">Unreviewed</option>
        </select>
        <span className="text-sm text-gray-500">{filtered.length} documents</span>
      </div>

      {isLoading ? (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="card text-center py-12">
          <FileText className="mx-auto text-gray-400 mb-4" size={48} />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            {documents.length === 0 ? 'No Documents Yet' : 'No Matching Documents'}
          </h3>
          <p className="text-gray-500">
            {documents.length === 0
              ? 'Generate documents from job detail pages or run the pipeline.'
              : 'Try changing your filters.'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((doc) => (
            <div key={doc.id} className="card flex items-center gap-4">
              {/* Type badge */}
              <div
                className={`p-2.5 rounded-lg ${
                  doc.document_type === 'resume'
                    ? 'bg-blue-100 text-blue-600'
                    : 'bg-purple-100 text-purple-600'
                }`}
              >
                <FileText size={20} />
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-900 truncate">
                    {doc.job_title || 'Untitled Job'}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${
                      doc.document_type === 'resume'
                        ? 'bg-blue-50 text-blue-600'
                        : 'bg-purple-50 text-purple-600'
                    }`}
                  >
                    {doc.document_type === 'resume' ? 'Resume' : 'Cover Letter'}
                  </span>
                </div>
                <div className="text-sm text-gray-500 flex items-center gap-3 mt-0.5">
                  <span>{doc.job_company || 'Unknown Company'}</span>
                  {doc.overall_score > 0 && (
                    <span className="text-xs bg-gray-100 px-1.5 py-0.5 rounded">
                      Score: {doc.overall_score.toFixed(0)}%
                    </span>
                  )}
                  <span>{formatDate(doc.created_at)}</span>
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2">
                {/* Job URL link */}
                {doc.job_url && (
                  <a
                    href={doc.job_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-2 text-gray-400 hover:text-blue-600 rounded-lg hover:bg-blue-50 transition-colors"
                    title="View job posting"
                  >
                    <ExternalLink size={18} />
                  </a>
                )}

                {/* Reviewed toggle */}
                <button
                  onClick={() =>
                    reviewMutation.mutate({ docId: doc.id, reviewed: !doc.reviewed })
                  }
                  className={`p-2 rounded-lg transition-colors ${
                    doc.reviewed
                      ? 'text-green-600 bg-green-50 hover:bg-green-100'
                      : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
                  }`}
                  title={doc.reviewed ? 'Mark as unreviewed' : 'Mark as reviewed'}
                >
                  {doc.reviewed ? <CheckSquare size={18} /> : <Square size={18} />}
                </button>

                {/* Good/Not Good toggles */}
                <button
                  onClick={() =>
                    reviewMutation.mutate({
                      docId: doc.id,
                      is_good: doc.is_good === true ? null : true,
                    })
                  }
                  className={`p-2 rounded-lg transition-colors ${
                    doc.is_good === true
                      ? 'text-green-600 bg-green-50'
                      : 'text-gray-400 hover:text-green-600 hover:bg-green-50'
                  }`}
                  title="Good"
                >
                  <ThumbsUp size={16} />
                </button>
                <button
                  onClick={() =>
                    reviewMutation.mutate({
                      docId: doc.id,
                      is_good: doc.is_good === false ? null : false,
                    })
                  }
                  className={`p-2 rounded-lg transition-colors ${
                    doc.is_good === false
                      ? 'text-red-600 bg-red-50'
                      : 'text-gray-400 hover:text-red-600 hover:bg-red-50'
                  }`}
                  title="Not good"
                >
                  <ThumbsDown size={16} />
                </button>

                {/* Download */}
                {doc.pdf_path && (
                  <button
                    onClick={() => handleDownload(doc)}
                    className="p-2 text-gray-400 hover:text-primary-600 rounded-lg hover:bg-primary-50 transition-colors"
                    title="Download PDF"
                  >
                    <Download size={18} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
