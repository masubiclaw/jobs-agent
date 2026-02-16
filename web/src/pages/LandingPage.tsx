import { Link } from 'react-router-dom'
import { Briefcase, Target, FileText, ArrowRight, CheckCircle } from 'lucide-react'

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-primary-50 to-white">
      {/* Header */}
      <header className="px-6 py-4 flex items-center justify-between max-w-6xl mx-auto">
        <h1 className="text-2xl font-bold text-primary-600">Jobs Agent</h1>
        <div className="flex items-center gap-3">
          <Link to="/login" className="text-sm font-medium text-gray-600 hover:text-gray-900 px-4 py-2">
            Sign in
          </Link>
          <Link to="/register" className="btn btn-primary text-sm">
            Get Started
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="px-6 py-16 md:py-24 text-center max-w-4xl mx-auto">
        <h2 className="text-4xl md:text-5xl font-bold text-gray-900 leading-tight">
          Find your next role,{' '}
          <span className="text-primary-600">faster</span>
        </h2>
        <p className="mt-6 text-lg md:text-xl text-gray-600 max-w-2xl mx-auto">
          Jobs Agent matches you with the right opportunities and generates tailored
          resumes and cover letters — so you can focus on landing the interview.
        </p>
        <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link to="/register" className="btn btn-primary text-base px-8 py-3 flex items-center gap-2">
            Create Free Account <ArrowRight size={18} />
          </Link>
          <Link to="/login" className="text-base text-gray-500 hover:text-gray-700 font-medium">
            Already have an account? Sign in
          </Link>
        </div>
      </section>

      {/* How it works */}
      <section className="px-6 py-16 max-w-6xl mx-auto">
        <h3 className="text-2xl font-bold text-center text-gray-900 mb-12">
          How it works
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="text-center p-6">
            <div className="w-14 h-14 bg-primary-100 rounded-xl flex items-center justify-center mx-auto mb-4">
              <Briefcase className="text-primary-600" size={28} />
            </div>
            <h4 className="text-lg font-semibold mb-2">1. Browse Jobs</h4>
            <p className="text-gray-600">
              Search through curated job listings from top companies, or add your own opportunities.
            </p>
          </div>
          <div className="text-center p-6">
            <div className="w-14 h-14 bg-green-100 rounded-xl flex items-center justify-center mx-auto mb-4">
              <Target className="text-green-600" size={28} />
            </div>
            <h4 className="text-lg font-semibold mb-2">2. See Your Matches</h4>
            <p className="text-gray-600">
              Our matching engine analyzes each job against your profile and skills to find your best fits.
            </p>
          </div>
          <div className="text-center p-6">
            <div className="w-14 h-14 bg-purple-100 rounded-xl flex items-center justify-center mx-auto mb-4">
              <FileText className="text-purple-600" size={28} />
            </div>
            <h4 className="text-lg font-semibold mb-2">3. Generate & Apply</h4>
            <p className="text-gray-600">
              Get a tailored resume and cover letter for each job, then apply with confidence.
            </p>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="px-6 py-16 bg-gray-50">
        <div className="max-w-3xl mx-auto">
          <h3 className="text-2xl font-bold text-center text-gray-900 mb-10">
            Everything you need for your job search
          </h3>
          <div className="space-y-4">
            {[
              'Smart job matching based on your skills and experience',
              'AI-generated resumes tailored to each job posting',
              'Cover letters that highlight your relevant strengths',
              'Track your applications from search to offer',
              'Works on desktop and mobile',
            ].map((feature) => (
              <div key={feature} className="flex items-start gap-3">
                <CheckCircle className="text-green-500 flex-shrink-0 mt-0.5" size={20} />
                <span className="text-gray-700">{feature}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="px-6 py-16 text-center">
        <h3 className="text-2xl font-bold text-gray-900 mb-4">
          Ready to get started?
        </h3>
        <p className="text-gray-600 mb-8">
          Create your profile and find your next role in minutes.
        </p>
        <Link to="/register" className="btn btn-primary text-base px-8 py-3">
          Sign Up Free
        </Link>
      </section>

      {/* Footer */}
      <footer className="px-6 py-8 border-t border-gray-200 text-center text-sm text-gray-500">
        Jobs Agent
      </footer>
    </div>
  )
}
