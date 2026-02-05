import { FileText, Download, Info } from 'lucide-react'

export default function DocumentsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Documents</h1>
        <p className="text-gray-600 mt-1">
          Generated resumes and cover letters
        </p>
      </div>

      <div className="card">
        <div className="flex items-start gap-4">
          <div className="p-3 bg-blue-100 rounded-lg">
            <Info className="text-blue-600" size={24} />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">How to Generate Documents</h3>
            <p className="text-gray-600 mt-1">
              To generate a resume or cover letter:
            </p>
            <ol className="mt-2 space-y-2 text-sm text-gray-600 list-decimal list-inside">
              <li>Make sure you have an active profile with your skills and experience</li>
              <li>Go to any job detail page</li>
              <li>Click "Generate Resume" or "Generate Cover Letter"</li>
              <li>The document will be automatically downloaded as a PDF</li>
            </ol>
          </div>
        </div>
      </div>

      <div className="card text-center py-12">
        <FileText className="mx-auto text-gray-400 mb-4" size={48} />
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          Document History Coming Soon
        </h3>
        <p className="text-gray-500">
          A full document history with re-download capability will be available in a future update.
        </p>
      </div>
    </div>
  )
}
