import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { jobsApi } from '../api'
import { ArrowLeft, Link as LinkIcon, FileText, Upload } from 'lucide-react'

type AddMethod = 'url' | 'text' | 'manual' | 'pdf'

export default function AddJobPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [method, setMethod] = useState<AddMethod>('url')
  const [error, setError] = useState('')

  // URL method
  const [jobUrl, setJobUrl] = useState('')

  // Text method
  const [plaintext, setPlaintext] = useState('')

  // Manual method
  const [manualData, setManualData] = useState({
    title: '',
    company: '',
    location: '',
    description: '',
    salary: '',
    url: '',
  })

  // PDF method
  const [pdfFile, setPdfFile] = useState<File | null>(null)

  const createMutation = useMutation({
    mutationFn: jobsApi.create,
    onSuccess: (job) => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      navigate(`/jobs/${job.id}`)
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { detail?: string } } }
      setError(error.response?.data?.detail || 'Failed to add job')
    },
  })

  const uploadMutation = useMutation({
    mutationFn: jobsApi.uploadPdf,
    onSuccess: (job) => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      navigate(`/jobs/${job.id}`)
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { detail?: string } } }
      setError(error.response?.data?.detail || 'Failed to parse PDF')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    switch (method) {
      case 'url':
        if (!jobUrl.trim()) {
          setError('Please enter a job URL')
          return
        }
        createMutation.mutate({ job_url: jobUrl })
        break

      case 'text':
        if (!plaintext.trim()) {
          setError('Please enter job description text')
          return
        }
        createMutation.mutate({ plaintext })
        break

      case 'manual':
        if (!manualData.title.trim() || !manualData.company.trim()) {
          setError('Title and company are required')
          return
        }
        createMutation.mutate(manualData)
        break

      case 'pdf':
        if (!pdfFile) {
          setError('Please select a PDF file')
          return
        }
        uploadMutation.mutate(pdfFile)
        break
    }
  }

  const isLoading = createMutation.isPending || uploadMutation.isPending

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate('/jobs')}
          className="p-2 hover:bg-gray-100 rounded-lg"
        >
          <ArrowLeft size={20} />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Add Job</h1>
          <p className="text-gray-600 mt-1">
            Add a job using URL, text, manual entry, or PDF upload
          </p>
        </div>
      </div>

      {/* Method selector */}
      <div className="card">
        <div className="flex border-b border-gray-200 mb-6">
          {[
            { id: 'url', label: 'From URL', icon: LinkIcon },
            { id: 'text', label: 'Paste Text', icon: FileText },
            { id: 'manual', label: 'Manual Entry', icon: FileText },
            { id: 'pdf', label: 'Upload PDF', icon: Upload },
          ].map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setMethod(id as AddMethod)}
              className={`flex items-center gap-2 px-4 py-3 border-b-2 transition-colors ${
                method === id
                  ? 'border-primary-600 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              <Icon size={18} />
              {label}
            </button>
          ))}
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* URL method */}
          {method === 'url' && (
            <div>
              <label className="label">Job URL</label>
              <input
                type="url"
                value={jobUrl}
                onChange={(e) => setJobUrl(e.target.value)}
                className="input"
                placeholder="https://example.com/job/123"
              />
              <p className="mt-1 text-sm text-gray-500">
                Supports Indeed, LinkedIn, Glassdoor, Greenhouse, Lever, and more
              </p>
            </div>
          )}

          {/* Text method */}
          {method === 'text' && (
            <div>
              <label className="label">Job Description</label>
              <textarea
                value={plaintext}
                onChange={(e) => setPlaintext(e.target.value)}
                className="input"
                rows={10}
                placeholder="Paste the full job description here..."
              />
              <p className="mt-1 text-sm text-gray-500">
                Our AI will extract the job details from the text
              </p>
            </div>
          )}

          {/* Manual method */}
          {method === 'manual' && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Job Title *</label>
                  <input
                    type="text"
                    value={manualData.title}
                    onChange={(e) =>
                      setManualData({ ...manualData, title: e.target.value })
                    }
                    className="input"
                    required
                  />
                </div>
                <div>
                  <label className="label">Company *</label>
                  <input
                    type="text"
                    value={manualData.company}
                    onChange={(e) =>
                      setManualData({ ...manualData, company: e.target.value })
                    }
                    className="input"
                    required
                  />
                </div>
                <div>
                  <label className="label">Location</label>
                  <input
                    type="text"
                    value={manualData.location}
                    onChange={(e) =>
                      setManualData({ ...manualData, location: e.target.value })
                    }
                    className="input"
                    placeholder="City, State or Remote"
                  />
                </div>
                <div>
                  <label className="label">Salary</label>
                  <input
                    type="text"
                    value={manualData.salary}
                    onChange={(e) =>
                      setManualData({ ...manualData, salary: e.target.value })
                    }
                    className="input"
                    placeholder="$100,000 - $150,000"
                  />
                </div>
              </div>
              <div>
                <label className="label">Job URL</label>
                <input
                  type="url"
                  value={manualData.url}
                  onChange={(e) =>
                    setManualData({ ...manualData, url: e.target.value })
                  }
                  className="input"
                  placeholder="https://..."
                />
              </div>
              <div>
                <label className="label">Description</label>
                <textarea
                  value={manualData.description}
                  onChange={(e) =>
                    setManualData({ ...manualData, description: e.target.value })
                  }
                  className="input"
                  rows={6}
                  placeholder="Job description..."
                />
              </div>
            </div>
          )}

          {/* PDF method */}
          {method === 'pdf' && (
            <div>
              <label className="label">PDF File</label>
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
                <input
                  type="file"
                  accept=".pdf"
                  onChange={(e) => setPdfFile(e.target.files?.[0] || null)}
                  className="hidden"
                  id="pdf-upload"
                />
                <label
                  htmlFor="pdf-upload"
                  className="cursor-pointer flex flex-col items-center gap-2"
                >
                  <Upload className="text-gray-400" size={32} />
                  <span className="text-gray-600">
                    {pdfFile ? pdfFile.name : 'Click to upload PDF'}
                  </span>
                  <span className="text-sm text-gray-400">
                    or drag and drop
                  </span>
                </label>
              </div>
            </div>
          )}

          <div className="flex justify-end gap-4 pt-4">
            <button
              type="button"
              onClick={() => navigate('/jobs')}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="btn btn-primary"
            >
              {isLoading ? (
                <span className="flex items-center gap-2">
                  <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></span>
                  Adding...
                </span>
              ) : (
                'Add Job'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
