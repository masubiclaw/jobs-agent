import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { adminApi } from '../../api'
import { RefreshCw, Search, Trash2, CheckCircle, AlertCircle } from 'lucide-react'

export default function AdminScraperPage() {
  // Scraper state
  const [scraperCategories, setScraperCategories] = useState('')
  const [maxSources, setMaxSources] = useState(0)

  // Searcher state
  const [searchTerm, setSearchTerm] = useState('')
  const [searchLocation, setSearchLocation] = useState('')
  const [searchSites, setSearchSites] = useState('indeed,linkedin')
  const [resultsWanted, setResultsWanted] = useState(15)

  // Matcher state
  const [llmPass, setLlmPass] = useState(false)
  const [matcherLimit, setMatcherLimit] = useState(100)

  // Cleanup state
  const [daysOld, setDaysOld] = useState(30)
  const [checkUrls, setCheckUrls] = useState(false)

  // Status messages
  const [messages, setMessages] = useState<{ type: 'success' | 'error'; text: string }[]>([])

  const addMessage = (type: 'success' | 'error', text: string) => {
    setMessages((prev) => [...prev, { type, text }])
    setTimeout(() => {
      setMessages((prev) => prev.slice(1))
    }, 5000)
  }

  const scraperMutation = useMutation({
    mutationFn: () => adminApi.runScraper({
      categories: scraperCategories || undefined,
      max_sources: maxSources || undefined,
    }),
    onSuccess: (data) => addMessage('success', data.message),
    onError: () => addMessage('error', 'Failed to start scraper'),
  })

  const searcherMutation = useMutation({
    mutationFn: () => adminApi.runSearcher({
      search_term: searchTerm,
      location: searchLocation || undefined,
      sites: searchSites,
      results_wanted: resultsWanted,
    }),
    onSuccess: (data) => addMessage('success', data.message),
    onError: () => addMessage('error', 'Failed to start searcher'),
  })

  const matcherMutation = useMutation({
    mutationFn: () => adminApi.runMatcher({
      llm_pass: llmPass,
      limit: matcherLimit,
    }),
    onSuccess: (data) => addMessage('success', data.message),
    onError: () => addMessage('error', 'Failed to start matcher'),
  })

  const cleanupMutation = useMutation({
    mutationFn: () => adminApi.runCleanup({
      days_old: daysOld,
      check_urls: checkUrls,
    }),
    onSuccess: (data) => addMessage('success', data.message),
    onError: () => addMessage('error', 'Failed to start cleanup'),
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">System Operations</h1>
        <p className="text-gray-600 mt-1">
          Run scraper, searcher, matcher, and cleanup operations
        </p>
      </div>

      {/* Status messages */}
      {messages.length > 0 && (
        <div className="space-y-2">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`p-3 rounded-lg flex items-center gap-2 ${
                msg.type === 'success'
                  ? 'bg-green-50 text-green-700 border border-green-200'
                  : 'bg-red-50 text-red-700 border border-red-200'
              }`}
            >
              {msg.type === 'success' ? (
                <CheckCircle size={20} />
              ) : (
                <AlertCircle size={20} />
              )}
              {msg.text}
            </div>
          ))}
        </div>
      )}

      {/* Job Scraper */}
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <RefreshCw className="text-blue-600" size={24} />
          <h2 className="text-lg font-semibold">Job Scraper</h2>
        </div>
        <p className="text-gray-600 mb-4">
          Scrape job listings from company career pages defined in JobOpeningsLink.md
        </p>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="label">Categories (comma-separated)</label>
            <input
              type="text"
              value={scraperCategories}
              onChange={(e) => setScraperCategories(e.target.value)}
              className="input"
              placeholder="Leave empty for all"
            />
          </div>
          <div>
            <label className="label">Max Sources (0 for all)</label>
            <input
              type="number"
              value={maxSources}
              onChange={(e) => setMaxSources(parseInt(e.target.value) || 0)}
              className="input"
              min={0}
            />
          </div>
        </div>
        <button
          onClick={() => scraperMutation.mutate()}
          disabled={scraperMutation.isPending}
          className="btn btn-primary"
        >
          {scraperMutation.isPending ? 'Starting...' : 'Run Scraper'}
        </button>
      </div>

      {/* Job Searcher */}
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <Search className="text-green-600" size={24} />
          <h2 className="text-lg font-semibold">Job Searcher</h2>
        </div>
        <p className="text-gray-600 mb-4">
          Search job aggregators (Indeed, LinkedIn, Glassdoor, etc.) for listings
        </p>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="label">Search Term *</label>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="input"
              placeholder="Software Engineer"
              required
            />
          </div>
          <div>
            <label className="label">Location</label>
            <input
              type="text"
              value={searchLocation}
              onChange={(e) => setSearchLocation(e.target.value)}
              className="input"
              placeholder="Seattle, WA"
            />
          </div>
          <div>
            <label className="label">Sites</label>
            <input
              type="text"
              value={searchSites}
              onChange={(e) => setSearchSites(e.target.value)}
              className="input"
              placeholder="indeed,linkedin,glassdoor"
            />
          </div>
          <div>
            <label className="label">Results Wanted</label>
            <input
              type="number"
              value={resultsWanted}
              onChange={(e) => setResultsWanted(parseInt(e.target.value) || 15)}
              className="input"
              min={1}
              max={50}
            />
          </div>
        </div>
        <button
          onClick={() => searcherMutation.mutate()}
          disabled={searcherMutation.isPending || !searchTerm.trim()}
          className="btn btn-primary"
        >
          {searcherMutation.isPending ? 'Starting...' : 'Run Searcher'}
        </button>
      </div>

      {/* Job Matcher */}
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <RefreshCw className="text-purple-600" size={24} />
          <h2 className="text-lg font-semibold">Job Matcher</h2>
        </div>
        <p className="text-gray-600 mb-4">
          Analyze cached jobs against user profile using keyword and optional LLM matching
        </p>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="label">Max Jobs to Match</label>
            <input
              type="number"
              value={matcherLimit}
              onChange={(e) => setMatcherLimit(parseInt(e.target.value) || 100)}
              className="input"
              min={1}
              max={500}
            />
          </div>
          <div className="flex items-center">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={llmPass}
                onChange={(e) => setLlmPass(e.target.checked)}
                className="w-4 h-4 rounded border-gray-300"
              />
              <span>Enable LLM Pass (slower but more accurate)</span>
            </label>
          </div>
        </div>
        <button
          onClick={() => matcherMutation.mutate()}
          disabled={matcherMutation.isPending}
          className="btn btn-primary"
        >
          {matcherMutation.isPending ? 'Starting...' : 'Run Matcher'}
        </button>
      </div>

      {/* Cleanup */}
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <Trash2 className="text-red-600" size={24} />
          <h2 className="text-lg font-semibold">Cleanup</h2>
        </div>
        <p className="text-gray-600 mb-4">
          Remove old or dead job listings from the cache
        </p>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="label">Remove jobs older than (days)</label>
            <input
              type="number"
              value={daysOld}
              onChange={(e) => setDaysOld(parseInt(e.target.value) || 30)}
              className="input"
              min={1}
            />
          </div>
          <div className="flex items-center">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={checkUrls}
                onChange={(e) => setCheckUrls(e.target.checked)}
                className="w-4 h-4 rounded border-gray-300"
              />
              <span>Check if URLs are still valid (slow)</span>
            </label>
          </div>
        </div>
        <button
          onClick={() => cleanupMutation.mutate()}
          disabled={cleanupMutation.isPending}
          className="btn btn-danger"
        >
          {cleanupMutation.isPending ? 'Starting...' : 'Run Cleanup'}
        </button>
      </div>
    </div>
  )
}
